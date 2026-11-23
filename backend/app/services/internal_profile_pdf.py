"""Export the saved employee profile, including its electronic signature."""
import base64
from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from app.schemas.internal_registration import InternalRegistration


def internal_profile_pdf(registration, candidate_name):
    schema = InternalRegistration.model_json_schema()
    data = registration["data"]
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("SectionTitle", parent=styles["Heading2"], textColor=colors.HexColor("#a71920"), spaceBefore=14, spaceAfter=8))
    styles.add(ParagraphStyle("Entry", parent=styles["BodyText"], fontSize=9, leading=13, spaceAfter=6))
    styles.add(ParagraphStyle("SmallNote", parent=styles["BodyText"], fontSize=8, leading=11, textColor=colors.HexColor("#59636d")))
    story = [Paragraph("Porto Aurora TALENTOS", styles["Title"]), Paragraph("Ficha de inscrição para seleção interna", styles["Heading1"]),
             Paragraph("FORM-PPO-RH-002.01 · Confidencial", styles["SmallNote"]), Spacer(1, 5 * mm),
             Paragraph(escape(candidate_name), styles["Heading2"])]

    def text(value):
        return escape(str(value)).replace("\n", "<br/>")

    def render(model, values):
        if "$ref" in model:
            model = schema["$defs"][model["$ref"].split("/")[-1]]
        for key, raw in model.get("properties", {}).items():
            resolved = schema["$defs"][raw["$ref"].split("/")[-1]] if "$ref" in raw else raw
            if "anyOf" in resolved:
                resolved = next((item for item in resolved["anyOf"] if item.get("type") != "null"), {})
            title = raw.get("title", resolved.get("title", key))
            value = values.get(key)
            if resolved.get("type") == "object":
                story.append(Paragraph(text(title), styles["SectionTitle"]))
                if raw.get("description"):
                    story.append(Paragraph(text(raw["description"]), styles["SmallNote"]))
                render(resolved, value or {})
            elif resolved.get("type") == "array":
                story.append(Paragraph(text(title), styles["SectionTitle"]))
                for index, item in enumerate(value or [], 1):
                    story.append(Paragraph(f"{text(title)} — {index}", styles["Heading3"]))
                    render(resolved["items"], item)
                if not value:
                    story.append(Paragraph("Nenhum item informado.", styles["Entry"]))
            elif resolved.get("format") == "signature":
                story.append(Paragraph(text(title), styles["Heading3"]))
                if value:
                    content = BytesIO(base64.b64decode(value.split(",", 1)[1], validate=True))
                    image = Image(content)
                    image.drawWidth = 140 * mm
                    image.drawHeight = image.imageHeight * image.drawWidth / image.imageWidth
                    image.hAlign = "LEFT"
                    story.append(image)
                else:
                    story.append(Paragraph("Assinatura não registrada.", styles["Entry"]))
            else:
                if isinstance(value, bool):
                    value = "Sim" if value else "Não"
                elif value is None or value == "":
                    value = "Não informado"
                elif resolved.get("format") == "date":
                    value = "/".join(str(value).split("-")[::-1])
                story.append(Paragraph(f"<b>{text(title)}:</b> {text(value)}", styles["Entry"]))

    render(schema, data)
    story.append(Spacer(1, 6 * mm))
    saved = registration.get("saved_at")
    saved_label = datetime.fromisoformat(saved).astimezone(ZoneInfo("America/Fortaleza")).strftime("%d/%m/%Y %H:%M") if saved else "Não informado"
    status = "Declarações confirmadas" if registration.get("confirmed_at") else "Rascunho — declarações não confirmadas"
    story.append(Paragraph(f"Versão {registration.get('version', 0)} · Salva em {saved_label} · {status}", styles["SmallNote"]))
    story.append(Paragraph("Recomendação do gestor: área reservada à gestão, não preenchida pelo colaborador neste perfil.", styles["SmallNote"]))
    output = BytesIO()

    def footer(canvas, doc):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#59636d"))
        canvas.drawString(18 * mm, 12 * mm, "FORM-PPO-RH-002.01 · Confidencial")
        canvas.drawRightString(A4[0] - 18 * mm, 12 * mm, f"Página {doc.page}")

    SimpleDocTemplate(output, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=18 * mm,
                      bottomMargin=22 * mm, title="Ficha de seleção interna", author="Porto Aurora Talentos").build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
