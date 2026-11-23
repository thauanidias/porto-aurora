"""Populate the supplied OOXML template while preserving its original drawings."""
import base64
import hashlib
import json
import math
import re
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

from app.schemas.selection_registration import SelectionRegistration

TEMPLATE = Path(__file__).parents[1] / "documents" / "ficha-selecao-externa.xlsx"
TEMPLATE_SHA256 = "9734e64a767d3aa9e880e090263a25a90dd3113f2df5159b580e22392514cc03"
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def data_hash(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def external_profile_xlsx(registration):
    data, proof = registration["data"], registration.get("signature_record") or {}
    if not data or not registration.get("confirmed_at") or not data.get("declaration", {}).get("signature_image"):
        raise ValueError("A ficha ainda não foi concluída e assinada pelo candidato.")
    if proof.get("data_sha256") != data_hash(data) or proof.get("template_sha256") != TEMPLATE_SHA256:
        raise ValueError("A assinatura não corresponde à versão desta ficha.")
    source = TEMPLATE.read_bytes()
    if hashlib.sha256(source).hexdigest() != TEMPLATE_SHA256:
        raise ValueError("O modelo original da ficha não confere.")
    with zipfile.ZipFile(BytesIO(source)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    xml = files["xl/worksheets/sheet1.xml"].decode()
    root = ET.fromstring(xml)
    ns = lambda tag: f"{{{MAIN}}}{tag}"  # noqa: E731
    sheet_data = root.find(ns("sheetData"))
    if sheet_data is None:
        raise ValueError("Modelo sem células.")
    rows = {int(row.attrib["r"]): row for row in sheet_data}
    cells = {cell.get("r"): cell for row in sheet_data for cell in row}
    header_style = cells["A7"].get("s", "0")
    styles_xml = ET.fromstring(files["xl/styles.xml"])
    xfs = styles_xml.find(ns("cellXfs"))
    if xfs is None:
        raise ValueError("Modelo sem estilos.")
    wrap_styles = {}

    def wrapped(style):
        if style not in wrap_styles:
            new = ET.fromstring(ET.tostring(xfs[int(style)]))
            new.set("numFmtId", "49")
            new.set("applyNumberFormat", "1")
            new.set("applyAlignment", "1")
            alignment = new.find(ns("alignment"))
            if alignment is None:
                alignment = ET.Element(ns("alignment"))
                # OOXML requires alignment before protection/extLst. Excel rejects
                # a style that appends alignment after those existing children.
                position = next((index for index, child in enumerate(new) if child.tag in {ns("protection"), ns("extLst")}), len(new))
                new.insert(position, alignment)
            alignment.set("wrapText", "1")
            alignment.set("vertical", "center")
            wrap_styles[style] = str(len(xfs))
            xfs.append(new)
        return wrap_styles[style]

    body_style = wrapped(cells["B8"].get("s", "0"))

    def text_cell(parent, address, value, style):
        cell = ET.SubElement(parent, ns("c"), {"r": address, "t": "inlineStr", "s": style})
        node = ET.SubElement(ET.SubElement(cell, ns("is")), ns("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
        node.text = str(value if value is not None else "")
        return cell

    def put(address, value):
        match = re.search(r"\d+", address)
        if match is None:
            raise ValueError("Célula inválida.")
        row_id = int(match.group())
        if row_id not in rows:
            rows[row_id] = ET.SubElement(sheet_data, ns("row"), {"r": str(row_id)})
        cell = cells.get(address)
        style = cell.get("s", "0") if cell is not None else "0"
        if cell is not None:
            rows[row_id].remove(cell)
        cells[address] = text_cell(rows[row_id], address, value, wrapped(style))

    def day(value):
        return "/".join(value.split("-")[::-1]) if value else ""

    def answer(value):
        return value or "Não informado"

    p, docs, foreign, bank = (data.get(key, {}) for key in ("personal", "documents", "foreigner", "bank"))
    employment, languages, education, extra, declaration = (data.get(key, {}) for key in ("employment", "languages", "education", "complementary", "declaration"))
    values = {"A5": "Cargo pretendido: " + data.get("desired_position", ""), "B8": p.get("name", ""),
              "F8": "Data nasc.: " + day(p.get("birth_date")), "A9": "Estado civil: " + answer(p.get("marital_status")),
              "B12": p.get("mobile", ""), "A13": "E-mail: " + (p.get("email") or ""),
              "A16": "CPF: " + docs.get("cpf", ""), "H16": docs.get("cnh", ""), "J16": "Cat.: " + docs.get("cnh_category", ""),
              "B17": docs.get("rg", ""), "D17": "Órgão emissor: " + docs.get("issuing_authority", ""), "F17": "UF: " + docs.get("issuing_state", ""), "H17": day(docs.get("issued_on")),
              "A18": "Órgão de classe: " + docs.get("professional_council", ""), "F18": "Região: " + docs.get("council_region", ""), "H18": "Inscrição: " + docs.get("council_registration", ""),
              "A21": "Naturalizado? " + answer(foreign.get("naturalized")), "E21": answer(foreign.get("visa")), "G21": foreign.get("rne", ""), "H21": "Chegada: " + day(foreign.get("arrival_date")),
              "A23": "Banco: " + bank.get("bank_name", "") + " " + bank.get("bank_number", ""), "E23": "Agência: " + bank.get("branch", ""), "G23": "Conta corrente: " + bank.get("checking_account", ""),
              "A49": "Empresa: " + employment.get("company", ""), "G49": "Telefone: " + employment.get("phone", ""),
              "A52": "Cargo inicial: " + employment.get("initial_position", ""), "F52": "Cargo final: " + employment.get("final_position", ""),
              "A53": "Admissão: " + day(employment.get("admission_date")), "E53": "Saída: " + day(employment.get("departure_date")), "H53": "Último salário: " + str(employment.get("last_salary") if employment.get("last_salary") is not None else ""),
              "A54": "Benefícios: " + employment.get("benefits", ""), "A55": "Motivo da saída: " + employment.get("reason", ""), "A56": "Superior imediato: " + employment.get("supervisor", ""), "A57": "Principais atividades: " + employment.get("description", ""),
              "A75": "Parentesco com colaborador? " + answer(extra.get("related_employee")), "A76": "Nome: " + extra.get("employee_name", ""), "A77": "Parentesco: " + extra.get("relationship", ""),
              "A81": "Uniforme — Camisa: " + extra.get("shirt_size", "") + "   Calça: " + extra.get("pants_size", "") + "   Bota: " + extra.get("boot_size", ""),
              "A85": declaration.get("place", "") + ", " + day(declaration.get("date")), "G87": declaration.get("signature_name", "")}
    for address, base in ((p.get("address", {}), 10), (employment.get("address", {}), 50)):
        values.update({f"B{base}": address.get("street", ""), f"G{base}": "N.º " + address.get("number", ""), f"I{base}": address.get("complement", ""),
                       f"B{base+1}": address.get("neighborhood", ""), f"F{base+1}": address.get("city", ""), f"H{base+1}": address.get("state", ""), f"I{base+1}": "CEP: " + address.get("postal_code", "")})
    for index, dependent in enumerate(data.get("dependents", [])):
        row = 26 + index * 3
        values.update({f"B{row}": dependent.get("name", ""), f"I{row}": dependent.get("relationship", ""),
                       f"D{row+1}": dependent.get("mother_name", "") + " — CPF: " + dependent.get("mother_cpf", ""), f"I{row+1}": dependent.get("cns", ""),
                       f"B{row+2}": dependent.get("cpf", ""), f"E{row+2}": "RG: " + dependent.get("rg", ""), f"H{row+2}": day(dependent.get("birth_date")), f"J{row+2}": answer(dependent.get("income_tax_dependent"))})
    for row, key in ((62, "english"), (63, "spanish"), (64, "other_level")):
        for col, level in (("C", "Básico"), ("E", "Intermediário"), ("G", "Avançado"), ("I", "Fluente")):
            values[f"{col}{row}"] = ("X " if languages.get(key) == level else "") + level
    values["A64"] = "Outro: " + languages.get("other_language", "")
    values["F67"] = "Incompleto"
    values["A87"] = "Conteúdo integral e comprovante nas abas Dados completos e Comprovante."
    for row, key in enumerate(("high_school", "technical", "higher", "extension", "postgraduate", "masters"), 67):
        values[f"C{row}"] = ""
        values[f"D{row}"] = "Completo  ( X )" if education.get(key) == "Completo" else "Completo  (   )"
        values[f"F{row}"] = "Incompleto  ( X )" if education.get(key) == "Incompleto" else "Incompleto  (   )"
        values[f"E{row}"] = ""
        values[f"G{row}"] = ""
        if row > 67:
            values[f"H{row}"] = "Curso: " + (education.get(key + "_course") or "Não informado")
    if education.get("high_school", "Não informado") == "Não informado":
        values["H67"] = "Escolaridade não informada"
    related = extra.get("related_employee")
    def clean_negative(value):
        import unicodedata
        return unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode().strip().casefold()
    employee_name = extra.get("employee_name", "").strip()
    relationship = extra.get("relationship", "").strip()
    values["A76"] = "Nome do colaborador: " + (employee_name or ("Não se aplica" if related == "Não" else "Não informado"))
    values["A77"] = "Grau de parentesco: " + ("Não se aplica" if related == "Não" and clean_negative(relationship) in {"", "nao", "n/a", "nao se aplica"} else relationship or "Não informado")
    for row, key, title in ((78, "flexible_hours", "Flexibilidade de horário"), (79, "flexible_weekends", "Flexibilidade no fim de semana"), (80, "available_for_travel", "Disponibilidade para viagens")):
        values[f"A{row}"] = title + ": " + answer(extra.get(key))
        restriction = extra.get({78: "hours_restrictions", 79: "weekend_restrictions", 80: "travel_restrictions"}[row], "").strip()
        values[f"F{row}"] = "Restrições: " + ("Nenhuma" if clean_negative(restriction) in {"nao", "nenhuma", "sem restricoes"} else restriction or "Não informado")
    merges = root.find(ns("mergeCells"))
    if merges is None:
        raise ValueError("Modelo sem configuração de células mescladas.")
    for area in ("A5:J5", "A18:E18", "F18:G18", "H18:J18", "A21:C21", "H21:J21", "A49:F49", "G49:J49", "A52:E52", "F52:J52", "A53:D53", "E53:G53", "H53:J53", "A54:J54", "A55:J55", "A56:J56", "A57:J59", "A75:J75", "A76:J76", "A77:J77", "A81:J81", "A85:E85", "G85:J85", "A87:F87", "G87:J87", "A78:E78", "F78:J78", "A79:E79", "F79:J79", "A80:E80", "F80:J80", *[f"H{r}:J{r}" for r in range(67, 73)], *[f"D{r}:E{r}" for r in range(67, 73)], *[f"F{r}:G{r}" for r in range(67, 73)]):
        ET.SubElement(merges, ns("mergeCell"), {"ref": area})
    merges.set("count", str(len(merges)))
    for address, value in values.items():
        put(address, value)
    # Preserve the original form's hidden rows and compact layout. Bank and
    # dependent data remain available in the complete-data worksheet.
    for row_node in sheet_data:
        row_node[:] = sorted(row_node, key=lambda c: (len(re.sub(r"\d", "", c.get("r", ""))), re.sub(r"\d", "", c.get("r", ""))))
    sheet_data[:] = sorted(sheet_data, key=lambda r: int(r.get("r", "0")))
    rows[85].set("ht", "68")
    widths = [16.27, 10, 11.18, 15.18, 11.27, 13.27, 17, 13, 16.45, 18.82]
    merged_widths = {}
    for merged in merges:
        start, end = merged.get("ref", "A1:A1").split(":")
        first, last = ord(start[0]) - 65, ord(end[0]) - 65
        merged_widths[start] = sum(widths[first:last+1])
    for address, value in values.items():
        number = int(re.sub(r"\D", "", address))
        available = merged_widths.get(address, widths[ord(address[0])-65]) * .85
        needed = min(409, max(18, 12 * sum(max(1, math.ceil(len(line) / available)) for line in str(value).split("\n")) + 4))
        rows[number].set("ht", str(max(float(rows[number].get("ht", "18")), needed)))
        rows[number].set("customHeight", "1")
    ET.register_namespace("", MAIN)
    for tag, element in (("sheetData", sheet_data), ("mergeCells", merges)):
        replacement = ET.tostring(element, encoding="unicode")
        def replace_xml(_match: re.Match[str], rendered: str = replacement) -> str:
            return rendered
        xml = re.sub(r"<" + tag + r"\b.*?</" + tag + ">", replace_xml, xml, count=1, flags=re.S)
    files["xl/worksheets/sheet1.xml"] = xml.encode()
    image = base64.b64decode(declaration["signature_image"].split(",", 1)[1], validate=True)
    files["xl/media/candidate-signature.png"] = image
    anchor = '''<xdr:oneCellAnchor><xdr:from><xdr:col>6</xdr:col><xdr:colOff>19050</xdr:colOff><xdr:row>84</xdr:row><xdr:rowOff>19050</xdr:rowOff></xdr:from><xdr:ext cx="3048000" cy="745067"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="90202" name="Assinatura do candidato"/><xdr:cNvPicPr/></pic:nvPicPr><xdr:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:embed="rIdCandidateSignature"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>'''.replace("</pic:nvPicPr>", "</xdr:nvPicPr>")
    files["xl/drawings/drawing1.xml"] = files["xl/drawings/drawing1.xml"].replace(b"</xdr:wsDr>", (anchor + "</xdr:wsDr>").encode())
    files["xl/drawings/_rels/drawing1.xml.rels"] = files["xl/drawings/_rels/drawing1.xml.rels"].replace(b"</Relationships>", b'<Relationship Id="rIdCandidateSignature" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/candidate-signature.png"/></Relationships>')

    def extra_sheet(title, entries):
        sheet = ET.Element(ns("worksheet"))
        cols = ET.SubElement(sheet, ns("cols"))
        ET.SubElement(cols, ns("col"), {"min": "1", "max": "1", "width": "48", "customWidth": "1"})
        ET.SubElement(cols, ns("col"), {"min": "2", "max": "2", "width": "100", "customWidth": "1"})
        grid = ET.SubElement(sheet, ns("sheetData"))
        for index, (label, value) in enumerate([(title, "FORM-PPO-RH-002.02"), *entries], 1):
            row = ET.SubElement(grid, ns("row"), {"r": str(index), "ht": str(min(390, max(30, 15 * math.ceil(max(len(str(value)) / 90, len(label) / 44))))), "customHeight": "1"})
            text_cell(row, f"A{index}", label, header_style if index == 1 else body_style)
            text_cell(row, f"B{index}", value, header_style if index == 1 else body_style)
        ET.SubElement(sheet, ns("pageSetup"), {"paperSize": "9", "orientation": "portrait", "fitToWidth": "1", "fitToHeight": "0"})
        return ET.tostring(sheet, encoding="utf-8", xml_declaration=True)

    entries = []
    schema = SelectionRegistration.model_json_schema()

    def flatten(value, spec, prefix=""):
        if "$ref" in spec:
            spec = schema["$defs"][spec["$ref"].split("/")[-1]]
        if "anyOf" in spec:
            spec = next(s for s in spec["anyOf"] if s.get("type") != "null")
        if spec.get("type") == "object":
            for key, child in spec["properties"].items():
                if key != "signature_image":
                    flatten((value or {}).get(key), child, prefix + (" / " if prefix else "") + child.get("title", key))
        elif spec.get("type") == "array":
            for index, item in enumerate(value or []):
                flatten(item, spec["items"], prefix + f" {index+1}")
            if not value:
                entries.append((prefix, "Nenhum informado"))
        else:
            rendered = "Não informado" if value is None or value == "" else ("Sim" if value is True else "Não" if value is False else str(value))
            for index in range(0, len(rendered), 1500):
                entries.append((prefix + (" (continuação)" if index else ""), rendered[index:index+1500]))
    flatten(data, schema)
    signed_at = datetime.fromisoformat(proof["signed_at"]).astimezone(ZoneInfo("America/Fortaleza")).strftime("%d/%m/%Y %H:%M:%S (UTC-3)")
    files["xl/worksheets/sheet2.xml"] = extra_sheet("Ficha completa — dados informados", entries)
    files["xl/worksheets/sheet3.xml"] = extra_sheet("Comprovante da assinatura eletrônica", [("Protocolo", proof["protocol"]), ("Nome", declaration["signature_name"]), ("E-mail da conta autenticada", proof["email"]), ("Data e hora do servidor", signed_at), ("IP registrado", proof["ip"]), ("Versão da ficha", registration["version"]), ("SHA-256 dos dados e assinatura", proof["data_sha256"]), ("SHA-256 do modelo original", TEMPLATE_SHA256), ("Manifestação", "O candidato autenticado revisou as informações, registrou sua assinatura e confirmou as declarações da ficha.")])
    files["xl/workbook.xml"] = files["xl/workbook.xml"].replace(b"</sheets>", b'<sheet name="Dados completos" sheetId="2" r:id="rIdExternalData"/><sheet name="Comprovante" sheetId="3" r:id="rIdExternalProof"/></sheets>')
    files["xl/_rels/workbook.xml.rels"] = files["xl/_rels/workbook.xml.rels"].replace(b"</Relationships>", b'<Relationship Id="rIdExternalData" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/><Relationship Id="rIdExternalProof" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet3.xml"/></Relationships>')
    types = files["[Content_Types].xml"]
    if b'Extension="png"' not in types:
        types = types.replace(b"</Types>", b'<Default Extension="png" ContentType="image/png"/></Types>')
    files["[Content_Types].xml"] = types.replace(b"</Types>", b'<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/worksheets/sheet3.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
    xfs.set("count", str(len(xfs)))
    rendered_xfs = ET.tostring(xfs, encoding="unicode")
    files["xl/styles.xml"] = re.sub(r"<cellXfs\b.*?</cellXfs>", lambda _: rendered_xfs, files["xl/styles.xml"].decode(), count=1, flags=re.S).encode()
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()
