"""Runtime Excel export, using native OOXML without external spreadsheet services."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from xml.etree.ElementTree import Element, SubElement, tostring
from zoneinfo import ZoneInfo
import re

from sqlalchemy import select
from app.core.db import utcnow
from app.models import Application, Candidate, PipelineStage, StageHistory, User
from app.services.recruitment import candidate_view

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
LABELS = {"ACTIVE": "Em andamento", "RESERVE": "Reserva", "SELECTED": "Selecionado", "PRE_ADMISSION": "Pré-admissão", "HIRED": "Contratado", "REJECTED": "Não selecionado", "WITHDRAWN": "Desistência", "PUBLISHED": "Publicada", "PAUSED": "Pausada", "CLOSED": "Encerrada", "CANCELED": "Cancelada", "INTERNAL": "Interno", "EXTERNAL": "Externo", "BOTH": "Interno e externo"}

def label(value):
    return LABELS.get(value, value or "")

def local_date(value):
    return value.astimezone(ZoneInfo("America/Fortaleza")).strftime("%d/%m/%Y %H:%M") if value else ""

def col(number):
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result

def xml(element):
    return tostring(element, encoding="utf-8", xml_declaration=True)

def styles_xml():
    root = Element("styleSheet", xmlns=NS)
    fonts = SubElement(root, "fonts", count="5")
    for size, color, bold in [(11, "FF30343B", False), (16, "FFFFFFFF", True), (12, "FF30343B", True), (10, "FF68717C", False), (15, "FFA3181A", True)]:
        font = SubElement(fonts, "font")
        if bold:
            SubElement(font, "b")
        SubElement(font, "sz", val=str(size))
        SubElement(font, "color", rgb=color)
        SubElement(font, "name", val="Calibri")
    fills = SubElement(root, "fills", count="4")
    for pattern, color in [("none", None), ("gray125", None), ("solid", "FFA3181A"), ("solid", "FFF4F6F8")]:
        fill = SubElement(SubElement(fills, "fill"), "patternFill", patternType=pattern)
        if color:
            SubElement(fill, "fgColor", rgb=color)
            SubElement(fill, "bgColor", indexed="64")
    borders = SubElement(root, "borders", count="2")
    SubElement(borders, "border")
    border = SubElement(borders, "border")
    SubElement(SubElement(border, "bottom", style="hair"), "color", rgb="FFDCE1E7")
    SubElement(SubElement(root, "cellStyleXfs", count="1"), "xf", numFmtId="0", fontId="0", fillId="0", borderId="0")
    formats = SubElement(root, "cellXfs", count="8")
    for font, fill, border, horizontal in [(0, 0, 1, "left"), (1, 2, 0, "left"), (2, 0, 0, "left"), (3, 0, 0, "left"), (2, 2, 0, "left"), (0, 3, 1, "left"), (4, 0, 1, "center"), (4, 3, 1, "center")]:
        item = SubElement(formats, "xf", numFmtId="0", fontId=str(font), fillId=str(fill), borderId=str(border), xfId="0", applyFont="1", applyFill="1", applyAlignment="1", applyBorder="1")
        SubElement(item, "alignment", vertical="center", horizontal=horizontal, wrapText="1")
    # Column headers use a white font on the institutional red background.
    header_font = SubElement(fonts, "font")
    SubElement(header_font, "b")
    SubElement(header_font, "sz", val="11")
    SubElement(header_font, "color", rgb="FFFFFFFF")
    SubElement(header_font, "name", val="Calibri")
    fonts.set("count", "6")
    formats[4].set("fontId", "5")
    SubElement(SubElement(root, "cellStyles", count="1"), "cellStyle", name="Normal", xfId="0", builtinId="0")
    return xml(root)

def workbook_bytes(sheets, scope):
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        content = Element("Types", xmlns="http://schemas.openxmlformats.org/package/2006/content-types")
        for extension, mime in [("rels", "application/vnd.openxmlformats-package.relationships+xml"), ("xml", "application/xml")]:
            SubElement(content, "Default", Extension=extension, ContentType=mime)
        for path, mime in [("/xl/workbook.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"), ("/xl/styles.xml", "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml")]:
            SubElement(content, "Override", PartName=path, ContentType=mime)
        workbook = Element("workbook", xmlns=NS, attrib={"xmlns:r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"})
        tabs = SubElement(workbook, "sheets")
        defined_names = SubElement(workbook, "definedNames")
        relationships = Element("Relationships", xmlns="http://schemas.openxmlformats.org/package/2006/relationships")
        for index, (name, headers, data) in enumerate(sheets, 1):
            SubElement(content, "Override", PartName=f"/xl/worksheets/sheet{index}.xml", ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml")
            SubElement(tabs, "sheet", name=name, sheetId=str(index), attrib={"r:id": f"rId{index}"})
            SubElement(relationships, "Relationship", Id=f"rId{index}", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", Target=f"worksheets/sheet{index}.xml")
            sheet = Element("worksheet", xmlns=NS)
            properties = SubElement(sheet, "sheetPr")
            SubElement(properties, "pageSetUpPr", fitToPage="1")
            view = SubElement(SubElement(sheet, "sheetViews"), "sheetView", workbookViewId="0", showGridLines="0", zoomScale="90")
            SubElement(view, "pane", ySplit="4", topLeftCell="A5", activePane="bottomLeft", state="frozen")
            columns = SubElement(sheet, "cols")
            for column, header in enumerate(headers, 1):
                if name == "Resumo":
                    width = 60 if column == 1 else 24
                elif header in {"Vaga", "Pessoa", "Responsável", "Etapa", "Etapa atual"}:
                    width = 42 if header == "Vaga" else 34
                elif header in {"Divulgação", "Inscrição", "Encerramento", "Entrada", "Saída"}:
                    width = 23
                else:
                    width = max(20, len(header) + 5)
                SubElement(columns, "col", min=str(column), max=str(column), width=str(width), customWidth="1")
            body = SubElement(sheet, "sheetData")
            table = [["Porto Aurora | RELATÓRIO DE RECRUTAMENTO"], [("Resumo executivo" if name == "Resumo" else name) + " · " + scope], ["Data de emissão: " + local_date(utcnow()) + " · Horário de Fortaleza · Resultados atuais"], headers] + data
            note_row = len(table) + 2 if name == "Resumo" else None
            if note_row:
                table.extend([[], ["Critério de leitura: uma pessoa inscrita em duas vagas é contabilizada em cada vaga. Selecionados aguardam admissão; contratados concluíram o processo."]])
            for row_number, values in enumerate(table, 1):
                height = 44 if row_number == 1 else 30 if row_number in {2, 4} else 26 if row_number == 3 else 46 if row_number == note_row else 36 if name == "Resumo" else 34
                row = SubElement(body, "row", r=str(row_number), ht=str(height), customHeight="1")
                if row_number <= 3:
                    values = values + [""] * (len(headers) - len(values))
                for column, value in enumerate(values, 1):
                    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
                    style = 1 if row_number == 1 else 2 if row_number == 2 else 3 if row_number == 3 or row_number == note_row else 4 if row_number == 4 else (6 if row_number % 2 else 7) if numeric and name == "Resumo" else 5 if row_number % 2 == 0 else 0
                    cell = SubElement(row, "c", r=col(column) + str(row_number), s=str(style))
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        SubElement(cell, "v").text = str(value)
                    else:
                        cell.set("t", "inlineStr")
                        SubElement(SubElement(cell, "is"), "t", {"xml:space": "preserve"}).text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or ""))
            last = col(len(headers))
            quoted_name = "'" + name.replace("'", "''") + "'"
            SubElement(defined_names, "definedName", name="_xlnm.Print_Titles", localSheetId=str(index - 1)).text = quoted_name + "!$1:$4"
            SubElement(defined_names, "definedName", name="_xlnm.Print_Area", localSheetId=str(index - 1)).text = quoted_name + "!$A$1:$" + last + "$" + str(len(table))
            if name != "Resumo":
                SubElement(sheet, "autoFilter", ref=f"A4:{last}{max(4, len(table))}")
            if len(headers) > 1:
                merges = SubElement(sheet, "mergeCells", count="4" if note_row else "3")
                for row_number in (1, 2, 3):
                    SubElement(merges, "mergeCell", ref=f"A{row_number}:{last}{row_number}")
                if note_row:
                    SubElement(merges, "mergeCell", ref=f"A{note_row}:{last}{note_row}")
            SubElement(sheet, "printOptions", horizontalCentered="1", gridLines="0")
            SubElement(sheet, "pageMargins", left="0.3", right="0.3", top="0.45", bottom="0.45", header="0.2", footer="0.2")
            SubElement(sheet, "pageSetup", paperSize="9", orientation="landscape" if len(headers) > 4 else "portrait", fitToWidth="1", fitToHeight="0")
            footer = SubElement(sheet, "headerFooter")
            SubElement(footer, "oddFooter").text = "&LPorto Aurora Talentos · Uso interno&R Página &P de &N"
            archive.writestr(f"xl/worksheets/sheet{index}.xml", xml(sheet))
        SubElement(relationships, "Relationship", Id="styles", Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", Target="styles.xml")
        archive.writestr("[Content_Types].xml", xml(content))
        archive.writestr("xl/workbook.xml", xml(workbook))
        archive.writestr("xl/_rels/workbook.xml.rels", xml(relationships))
        archive.writestr("_rels/.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="workbook" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/styles.xml", styles_xml())

    return output.getvalue()

def build_report(db, actor, report, month):
    months = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    scope = ("Período: " + months[int(month[5:7]) - 1] + " de " + month[:4]) if month else "Vaga selecionada · histórico completo"
    totals = report["summary"]
    sheets = [("Resumo", ["INDICADORES CONSOLIDADOS", "QUANTIDADE"], [["Vagas", report["total"]], ["Candidatos por vaga", totals["candidates"]], ["Selecionados", totals["selected"]], ["Contratados", totals["hired"]], ["Em andamento", totals["in_progress"]], ["Não selecionados", totals["rejected"]], ["Desistências", totals["withdrawn"]]])]
    sheets.append(("Vagas", ["Código", "Vaga", "Situação", "Público", "Posições", "Divulgação", "Candidatos", "Selecionados", "Contratados", "Em andamento", "Não selecionados", "Desistências"], [[v["code"], v["title"], label(v["status"]), label(v["audience"]), v["quantity"], local_date(v["published_at"]), v["candidates"], v["selected"], v["hired"], v["in_progress"], v["rejected"], v["withdrawn"]] for v in report["items"]]))
    ids = [v["id"] for v in report["items"]]
    if "candidate.view" in actor.permissions and ids:
        applications = db.scalars(select(Application).where(Application.vacancy_id.in_(ids)).order_by(Application.created_at)).all()
        vacancies = {v["id"]: v for v in report["items"]}
        names = {}
        records = []
        for application in applications:
            candidate = db.get(Candidate, application.candidate_id)
            names[application.id] = candidate_view(db, actor, candidate, application)["name"]
            stage = db.get(PipelineStage, application.stage_id)
            records.append([vacancies[application.vacancy_id]["code"], vacancies[application.vacancy_id]["title"], names[application.id], label(application.recruitment_type), label(application.status), stage.name, local_date(application.created_at), local_date(application.closed_at)])
        sheets.append(("Candidaturas", ["Código da vaga", "Vaga", "Pessoa", "Público", "Situação", "Etapa atual", "Inscrição", "Encerramento"], records))
        history = []
        for entry in db.scalars(select(StageHistory).where(StageHistory.application_id.in_(list(names))).order_by(StageHistory.entered_at)):
            stage = db.get(PipelineStage, entry.stage_id)
            responsible = db.get(User, entry.changed_by) if entry.changed_by else None
            history.append([names[entry.application_id], vacancies[stage.vacancy_id]["title"], stage.name, local_date(entry.entered_at), local_date(entry.left_at), responsible.name if responsible else ""])
        sheets.append(("Histórico de etapas", ["Pessoa", "Vaga", "Etapa", "Entrada", "Saída", "Responsável"], history))
    return workbook_bytes(sheets, scope)
