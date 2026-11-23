"""Preserve the source Word document and append its electronic acceptance record."""

import base64
import hashlib
import io
import zipfile
from datetime import UTC
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from app.models import ConsentReceipt

SOURCE = Path(__file__).parents[1] / "documents" / "termo-consentimento-rs.docx"
DOCUMENT_CODE = "FORM-PPO-RH-002.09"
SOURCE_SHA256 = "2ab19f780309d904dd010c3afc972284889189d199c52a8214bdfc06d5b8e817"


def _run(text: str, bold: bool = False) -> str:
    properties = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f'<w:r>{properties}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def _paragraph(label: str, value: str = "") -> str:
    return (
        '<w:p><w:pPr><w:spacing w:after="160"/></w:pPr>'
        + _run(label, bold=True)
        + _run(value)
        + "</w:p>"
    )


def receipt_docx(receipt: ConsentReceipt) -> bytes:
    if receipt.document_code != DOCUMENT_CODE:
        raise ValueError("O comprovante não pertence ao termo de dados pessoais.")
    snapshot = receipt.document_snapshot or {}
    paragraphs = snapshot.get("paragraphs")
    if not isinstance(paragraphs, list) or not all(isinstance(p, str) for p in paragraphs):
        raise ValueError("Texto do aceite indisponível.")
    text_hash = hashlib.sha256("\n".join(paragraphs).encode()).hexdigest()
    if text_hash != receipt.document_sha256:
        raise ValueError("O texto do aceite não confere com o comprovante.")

    source = SOURCE.read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    if source_hash != SOURCE_SHA256:
        raise ValueError("O modelo Word original não confere com a versão do aceite.")
    accepted_at = receipt.created_at
    if accepted_at.tzinfo is None:
        accepted_at = accepted_at.replace(tzinfo=UTC)
    local_time = accepted_at.astimezone(ZoneInfo("America/Fortaleza"))
    signed_at = local_time.strftime("%d/%m/%Y %H:%M:%S (UTC−3)")
    image = snapshot.get("signature_image", "")
    electronic_hash = snapshot.get("electronic_signature_sha256", "")
    if electronic_hash:
        from app.services.electronic_acceptance import acceptance_signature
        import hmac
        if not hmac.compare_digest(electronic_hash, acceptance_signature(snapshot.get("acceptance_record", {}))):
            raise ValueError("O registro de aceite eletrônico não confere com o comprovante.")
    image_bytes = b""
    image_xml = ""
    if image:
        if hashlib.sha256(image.encode()).hexdigest() != snapshot.get("signature_sha256"):
            raise ValueError("A assinatura não confere com o comprovante.")
        image_bytes = base64.b64decode(image.split(",", 1)[1], validate=True)
        image_xml = '''<w:p><w:r><w:drawing><wp:inline xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><wp:extent cx="4572000" cy="1117600"/><wp:docPr id="90209" name="Assinatura do termo"/><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:pic><pic:nvPicPr><pic:cNvPr id="90209" name="Assinatura"/><pic:cNvPicPr/></pic:nvPicPr><pic:blipFill><a:blip r:embed="rIdConsentSignature"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill><pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="4572000" cy="1117600"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''
    signature = (
        '<w:p><w:pPr><w:spacing w:before="360" w:after="160"/></w:pPr>'
        + _run("Assinatura eletrônica", bold=True)
        + "</w:p>"
        + image_xml
        + _paragraph("Assinado eletronicamente por: ", receipt.name)
        + _paragraph("Data e hora: ", signed_at)
        + _paragraph("Protocolo do aceite: ", receipt.protocol)
        + (_paragraph("Forma de assinatura: ", "Aceite eletrônico após declaração de leitura integral no portal.")
           + _paragraph("Identificador da assinatura eletrônica (HMAC-SHA-256): ", electronic_hash) if electronic_hash else "")
    )
    appendix = (
        '<w:p><w:pPr><w:pageBreakBefore/><w:spacing w:after="300"/></w:pPr>'
        + _run("Comprovante de aceite eletrônico", bold=True)
        + "</w:p>"
        + _paragraph(
            "Documento: ",
            "Termo de Consentimento para Uso de Dados Pessoais no Recrutamento e Seleção",
        )
        + _paragraph("Código: ", receipt.document_code)
        + _paragraph("Protocolo: ", receipt.protocol)
        + _paragraph("Pessoa: ", receipt.name)
        + _paragraph("E-mail: ", receipt.email)
        + _paragraph("Data e hora do aceite: ", signed_at)
        + _paragraph("Endereço IP registrado: ", receipt.ip)
        + _paragraph(
            "Identificação: ",
            "Conta autenticada"
            if snapshot.get("identity") == "AUTHENTICATED"
            else "Nome e e-mail declarados no momento do aceite",
        )
        + _paragraph(
            "Manifestação: ",
            "A pessoa confirmou que leu e concordou com o termo apresentado no portal.",
        )
        + _paragraph("SHA-256 do texto apresentado: ", text_hash)
        + _paragraph("SHA-256 do arquivo Word original: ", source_hash)
        + (_paragraph("SHA-256 da assinatura registrada: ", snapshot["signature_sha256"]) if image else "")
        + '<w:p><w:pPr><w:spacing w:before="200"/></w:pPr>'
        + _run(
            "Este registro documenta o aceite eletrônico do termo apresentado no portal. "
            "O protocolo e os dados acima foram gerados automaticamente."
        )
        + "</w:p>"
    )

    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(output, "w") as result:
        for item in original.infolist():
            data = original.read(item.filename)
            if image_bytes and item.filename == "word/_rels/document.xml.rels":
                data = data.replace(b'</Relationships>', b'<Relationship Id="rIdConsentSignature" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/consent-signature.png"/></Relationships>')
            if image_bytes and item.filename == "[Content_Types].xml" and b'Extension="png"' not in data:
                data = data.replace(b'</Types>', b'<Default Extension="png" ContentType="image/png"/></Types>')
            if item.filename == "word/document.xml":
                xml = data.decode("utf-8")
                closing = xml.rfind("</w:body>")
                section = xml.rfind("<w:sectPr", 0, closing)
                if section < 0:
                    raise ValueError("Estrutura do termo Word inválida.")
                if snapshot.get("text_revision"):
                    body_start = xml.index(">", xml.index("<w:body")) + 1
                    xml = xml[:body_start] + "".join(_paragraph(text) for text in paragraphs if text.strip()) + xml[section:]
                    section = xml.rfind("<w:sectPr")
                data = (xml[:section] + signature + appendix + xml[section:]).encode("utf-8")
            result.writestr(item, data)
        if image_bytes:
            result.writestr("word/media/consent-signature.png", image_bytes)
    return output.getvalue()
