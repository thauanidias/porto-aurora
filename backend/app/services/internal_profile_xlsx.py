"""Fill the original workbook without rewriting its drawings, logos or hidden rows."""
import base64
import re
import textwrap
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
TEMPLATE = Path(__file__).parents[1] / "documents" / "ficha-selecao-interna.xlsx"


def internal_profile_xlsx(registration):
    data = registration["data"]
    with zipfile.ZipFile(TEMPLATE) as source:
        files = {name: source.read(name) for name in source.namelist()}
    xml = files["xl/worksheets/sheet2.xml"].decode()
    root = ET.fromstring(xml)
    sheet_data = root.find(f"{{{MAIN}}}sheetData")
    if sheet_data is None:
        raise ValueError("Modelo sem dados da planilha.")
    def ns(tag):
        return f"{{{MAIN}}}{tag}"
    rows = {int(row.attrib["r"]): row for row in sheet_data}
    cells = {cell.get("r"): cell for row in sheet_data for cell in row}
    ET.register_namespace("", MAIN)

    def put(address, value):
        if value is None:
            value = ""
        cell = cells.get(address)
        if cell is None:
            match = re.search(r"\d+", address)
            if match is None:
                raise ValueError("Endereço de célula inválido.")
            row_id = int(match.group())
            if row_id not in rows:
                rows[row_id] = ET.SubElement(sheet_data, ns("row"), {"r": str(row_id)})
            cell = ET.SubElement(rows[row_id], ns("c"), {"r": address})
            cells[address] = cell
        for child in list(cell):
            cell.remove(child)
        cell.set("t", "inlineStr")
        text = ET.SubElement(ET.SubElement(cell, ns("is")), ns("t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
        text.text = str(value)

    def day(value):
        return "/".join(value.split("-")[::-1]) if value else ""

    def check(value):
        return f"({'X' if value == 'Sim' else ' '}) Sim   ({'X' if value == 'Não' else ' '}) Não"

    if not registration.get("confirmed_at"):
        put("I1", "FORM-PPO-RH-002.01\nClassificação: confidencial\nRASCUNHO — declarações não confirmadas")

    personal, bank, employment = (data.get(key, {}) for key in ("personal", "bank", "employment"))
    address = personal.get("address", {})
    put("C5", data.get("desired_position", ""))
    for cell, value in {"B8": personal.get("name", ""), "I8": personal.get("employee_number", ""),
        "A9": "Data Nasc.: " + day(personal.get("birth_date")), "D9": personal.get("age", ""),
        "B11": address.get("street", ""), "G11": "Nº: " + address.get("number", ""), "I11": address.get("complement", ""),
        "B12": address.get("neighborhood", ""), "F12": address.get("city", ""), "H12": "UF: " + address.get("state", ""),
        "J12": address.get("postal_code", ""), "B13": personal.get("mobile", ""), "A14": "Email: " + (personal.get("email") or ""),
        "A17": "Banco: " + bank.get("bank_name", "") + " " + bank.get("bank_number", ""), "F17": bank.get("branch", ""),
        "H17": bank.get("checking_account", "")}.items():
        put(cell, value)
    marital = personal.get("marital_status")
    put("A10", "Estado civil: " + "  ".join(f"({'X' if marital == option else ' '}) {option}" for option in ["Solteiro", "Casado", "Viúvo", "Marital", "Separado", "Divorciado"]))
    for index, dependent in enumerate(data.get("dependents", [])):
        row = 19 + index * 3
        for cell, value in {f"B{row}": dependent.get("name", ""), f"I{row}": dependent.get("relationship", ""),
            f"D{row + 1}": dependent.get("mother_name", "") + (" · CPF: " + dependent["mother_cpf"] if dependent.get("mother_cpf") else ""),
            f"I{row + 1}": dependent.get("cns", ""), f"B{row + 2}": dependent.get("cpf", ""),
            f"F{row + 2}": dependent.get("rg", ""), f"H{row + 2}": day(dependent.get("birth_date")),
            f"J{row + 2}": check(dependent.get("income_tax_dependent"))}.items():
            put(cell, value)
    for cell, value in {"A40": "Data de admissão no Porto Aurora: " + day(employment.get("admission_date")),
        "G40": "Área que trabalha: " + employment.get("department", ""), "A41": "Cargo: " + employment.get("position", ""),
        "G41": "Superior imediato: " + employment.get("supervisor", ""),
        "C42": (day(employment.get("vacation_start")) + " a " + day(employment.get("vacation_end"))) if employment.get("vacation_start") or employment.get("vacation_end") else "",
        "A43": "Flexibilidade de horário? " + check(employment.get("flexible_hours")),
        "F43": "Restrições: " + employment.get("hours_restrictions", ""),
        "A44": "Flexibilidade no final de semana? " + check(employment.get("flexible_weekends")),
        "F44": "Restrições: " + employment.get("weekend_restrictions", ""),
        "A45": "Possui parentesco com colaborador do Porto Aurora? " + check(employment.get("related_employee")),
        "A46": "Nome do colaborador: " + employment.get("relative_name", ""),
        "A47": "Grau de parentesco: " + employment.get("relationship", "")}.items():
        put(cell, value)
    systems = [("word", "Word"), ("excel", "Excel"), ("powerpoint", "PowerPoint"), ("power_bi", "Power BI"), ("access", "Access")]
    put("A48", "Conhecimento em sistemas: " + "  ".join(f"{name} ({'X' if employment.get(key) else ' '})" for key, name in systems) + "  Outros: " + employment.get("other_systems", ""))
    languages = data.get("languages", {})
    for row, key in [(51, "english"), (52, "spanish"), (53, "other_level")]:
        for column, level in [("C", "Básico"), ("E", "Intermediário"), ("G", "Avançado"), ("I", "Fluente")]:
            put(f"{column}{row}", f"{level} ({'X' if languages.get(key) == level else ' '})")
    put("A53", "Outro: " + languages.get("other_language", ""))
    education = data.get("education", {})
    for row, key in [(56, "high_school"), (57, "technical"), (58, "higher"), (59, "extension"), (60, "postgraduate"), (61, "masters")]:
        status = education.get(key, "Não informado")
        put(f"B{row}", "(X)" if status in {"Completo", "Incompleto"} else "( )")
        put(f"E{row}", "(X)" if status == "Completo" else "( )")
        if row != 56 or status == "Incompleto":
            put(f"G{row}", "(X)" if status == "Incompleto" else "( )")
        if row == 56 and status == "Incompleto":
            put("F56", "Incompleto")
        if row != 56:
            put(f"H{row}", "Curso: " + education.get(key + "_course", ""))
    lines = []
    for line in data.get("motivation", "").splitlines():
        lines.extend(textwrap.wrap(line, width=110) or [""])
    per_row = max(1, (len(lines) + 11) // 12)
    for index in range(12):
        put(f"A{64 + index}", "\n".join(lines[index * per_row:(index + 1) * per_row]))
        if per_row > 1:
            rows[64 + index].set("ht", str(min(409, per_row * 14 + 4)))
            rows[64 + index].set("customHeight", "1")
    for index, item in enumerate(data.get("transport", [])):
        row = 92 + index
        put(f"A{row}", "Qtd diária: " + str(item.get("daily_quantity") or ""))
        put(f"C{row}", "Meio de transporte: " + item.get("transport", ""))
        put(f"I{row}", "Tarifa R$: " + str(item.get("fare") if item.get("fare") is not None else ""))
    union = data.get("union", {})
    put("H97", check(union.get("paid")))
    put("B98", "Entidade sindical: " + union.get("entity_name", ""))
    put("I98", "Valor: " + str(union.get("amount") if union.get("amount") is not None else ""))
    put("A99", "CNPJ entidade sindical: " + union.get("cnpj", ""))
    put("F99", "Código entidade sindical: " + union.get("entity_code", ""))
    declaration = data.get("declaration", {})
    put("A107", declaration.get("place", "") + (", " if declaration.get("place") else "") + day(declaration.get("date")))
    put("G109", declaration.get("signature_name", ""))
    merges = root.find(ns("mergeCells"))
    if merges is None:
        raise ValueError("Modelo sem configuração de células mescladas.")
    for area in ["A9:B9", "A40:F40", "G40:J40", "A41:F41", "G41:J41", "A42:B42", "C42:J42", "A43:E43", "F43:J43", "A44:E44", "F44:J44", "A45:J45", "A46:J46", "A47:J47", "A48:J49", "A53:B53", "A107:E107", "G109:J109", *[f"A{r}:J{r}" for r in range(64, 76)], *[f"H{r}:J{r}" for r in range(57, 62)]]:
        ET.SubElement(merges, ns("mergeCell"), {"ref": area})
    merges.set("count", str(len(merges)))
    # Preserve every template style; add wrapping only for the motivation lines.
    styles_xml = files["xl/styles.xml"].decode()
    styles = ET.fromstring(styles_xml)
    xfs = styles.find(ns("cellXfs"))
    if xfs is None:
        raise ValueError("Modelo sem estilos de células.")
    for row in range(64, 76):
        target_cell = cells[f"A{row}"]
        original = xfs[int(target_cell.get("s", "0"))]
        new = ET.fromstring(ET.tostring(original))
        alignment = new.find(ns("alignment"))
        if alignment is None:
            alignment = ET.SubElement(new, ns("alignment"))
        alignment.set("wrapText", "1")
        alignment.set("vertical", "top")
        target_cell.set("s", str(len(xfs)))
        xfs.append(new)
    xfs.set("count", str(len(xfs)))
    files["xl/styles.xml"] = re.sub(r"<cellXfs\b.*?</cellXfs>", lambda _: ET.tostring(xfs, encoding="unicode"), styles_xml, count=1, flags=re.S).encode()
    signature = declaration.get("signature_image")
    if signature:
        rows[107].set("ht", "65")
        rows[107].set("customHeight", "1")
        files["xl/media/employee-signature.png"] = base64.b64decode(signature.split(",", 1)[1], validate=True)
        drawing = files["xl/drawings/drawing2.xml"].decode()
        anchor = '''<xdr:oneCellAnchor><xdr:from><xdr:col>6</xdr:col><xdr:colOff>19050</xdr:colOff><xdr:row>106</xdr:row><xdr:rowOff>19050</xdr:rowOff></xdr:from><xdr:ext cx="3048000" cy="745067"/><xdr:pic><xdr:nvPicPr><xdr:cNvPr id="10000" name="Assinatura eletrônica do colaborador"/><xdr:cNvPicPr/></xdr:nvPicPr><xdr:blipFill><a:blip xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" r:embed="rIdEmployeeSignature"/><a:stretch><a:fillRect/></a:stretch></xdr:blipFill><xdr:spPr><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></xdr:spPr></xdr:pic><xdr:clientData/></xdr:oneCellAnchor>'''
        files["xl/drawings/drawing2.xml"] = drawing.replace("</xdr:wsDr>", anchor + "</xdr:wsDr>").encode()
        rels = files["xl/drawings/_rels/drawing2.xml.rels"].decode()
        relation = '<Relationship Id="rIdEmployeeSignature" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/employee-signature.png"/>'
        files["xl/drawings/_rels/drawing2.xml.rels"] = rels.replace("</Relationships>", relation + "</Relationships>").encode()
    xml = re.sub(r"<sheetData\b.*?</sheetData>", lambda _: ET.tostring(sheet_data, encoding="unicode"), xml, count=1, flags=re.S)
    xml = re.sub(r"<mergeCells\b.*?</mergeCells>", lambda _: ET.tostring(merges, encoding="unicode"), xml, count=1, flags=re.S)
    files["xl/worksheets/sheet2.xml"] = xml.encode()
    # Open directly on the original internal-selection tab.
    book = files["xl/workbook.xml"].decode()
    book = re.sub(r'activeTab="\d+"', 'activeTab="1"', book)
    files["xl/workbook.xml"] = book.encode()
    output = BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as result:
        for name, content in files.items():
            result.writestr(name, content)
    return output.getvalue()
