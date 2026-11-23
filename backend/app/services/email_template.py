"""Shared, email-client-compatible Porto Aurora notification presentation."""

import re
from html import escape
from pathlib import Path

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "porto-aurora-logo.png"



def render_email(subject: str, body: str, *, template: str = "default") -> str:
    if template == "rh-welcome":
        from app.services.welcome_email_template import render_welcome
        return render_welcome(subject, body)
    # Escape all user content before adding markup; preserve token-bearing URLs.
    def paragraph(text: str) -> str:
        pieces = re.split(r"(https?://[^\s<>]+)", text)
        content = "".join(
            '<a href="' + escape(piece, quote=True) + '" style="color:#145c67;text-decoration:underline;word-break:break-all">'
            + escape(piece) + '</a>' if re.fullmatch(r"https?://[^\s<>]+", piece)
            else escape(piece).replace("\n", "<br>") for piece in pieces
        )
        return '<p style="margin:0 0 22px;font-size:16px;line-height:26px;color:#292929">' + content + '</p>'

    paragraphs = "".join(paragraph(p) for p in body.replace("\r\n", "\n").split("\n\n") if p.strip())
    is_preview = subject.startswith(("[PRÉVIA", "[AVALIAÇÃO"))
    clean_subject = re.sub(r"^\[(?:PRÉVIA|AVALIAÇÃO)[^\]]*\]\s*", "", subject)
    is_test = subject.startswith("Teste de envio") or is_preview
    title = "Tudo pronto para nos conectarmos." if subject.startswith("Teste de envio") else clean_subject.removesuffix(" — Porto Aurora Talentos")
    label = "TESTE DE COMUNICAÇÃO" if is_test else "NOTIFICAÇÃO"
    note_title = "Você não precisa realizar nenhuma ação." if is_test else "Confira as orientações"
    note_body = "Esta mensagem serve apenas para conferir o recebimento e a apresentação dos e-mails do Porto Aurora Talentos." if is_test else "Quando houver uma atividade pendente, utilize o link desta mensagem para consultar os detalhes no portal."
    signature = '<p style="margin:0 0 24px;color:#292929;font-size:15px;line-height:24px">Atenciosamente,<br><strong>Equipe de Recursos Humanos</strong><br>Porto Aurora</p>'
    urls = re.findall(r"https?://[^\s<>]+", body)
    button = ""
    if is_preview:
        button = '<p style="margin:24px 0"><span style="display:inline-block;padding:15px 24px;background:#145c67;background-image:linear-gradient(#145c67,#145c67);color:#ffffff;-webkit-text-fill-color:#ffffff;border-radius:6px;font-size:16px;font-weight:bold">Confirmar e-mail e criar senha</span><br><span style="font-size:12px;color:#292929">Botão ilustrativo, sem ação nesta prévia.</span></p>'
    if urls and not is_test:
        label_button = "Confirmar e-mail e criar senha" if "crie sua senha" in subject else "Acessar Porto Aurora Talentos"
        button = '<table role="presentation" cellspacing="0" cellpadding="0" style="margin:24px 0"><tr><td class="brand-background" bgcolor="#145c67" style="border-radius:6px;background:#145c67;background-image:linear-gradient(#145c67,#145c67);"><a href="' + escape(urls[0], quote=True) + '" style="display:inline-block;padding:15px 24px;color:#ffffff;-webkit-text-fill-color:#ffffff;font-size:16px;font-weight:bold;text-decoration:none">' + label_button + '</a></td></tr></table>'
    return f'''<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light">
<style>
:root {{ color-scheme:light; supported-color-schemes:light; }}
@media (prefers-color-scheme:dark) {{
.email-page {{ background-color:#f3f4f6 !important; }}
.email-card, .email-content {{ background-color:#ffffff !important; color:#292929 !important; }}
.brand-background {{ background-color:#145c67 !important; background-image:linear-gradient(#145c67,#145c67) !important; }}
}}
[data-ogsc] .email-card, [data-ogsc] .email-content {{ background-color:#ffffff !important; color:#292929 !important; }}
[data-ogsc] .brand-background {{ background-color:#145c67 !important; background-image:linear-gradient(#145c67,#145c67) !important; }}
</style><title>{escape(subject)}</title></head>
<body class="email-page" style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#292929">
<table class="email-page" role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#f3f4f6" style="background:#f3f4f6"><tr><td align="center" style="padding:20px 12px">
<table class="email-card" bgcolor="#ffffff" role="presentation" width="600" cellspacing="0" cellpadding="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:12px">
<tr><td align="center" class="brand-background" bgcolor="#145c67" style="padding:32px 24px 26px;border-radius:12px 12px 0 0;background:#145c67;background-image:linear-gradient(#145c67,#145c67);">
<span style="display:inline-block;background:#ffffff;padding:14px 18px;border-radius:8px"><img src="cid:porto-aurora-logo" width="240" alt="Porto Aurora" style="display:block;width:240px;max-width:100%;height:auto;border:0;color:#145c67"></span>
</td></tr>
<tr><td class="email-content" bgcolor="#ffffff" style="padding:34px 30px 12px;background:#ffffff;color:#292929">
<p style="margin:0 0 12px;color:#292929;font-size:11px;line-height:18px;letter-spacing:2px;font-weight:bold">{label}</p>
<h1 style="margin:0 0 26px;color:#292929;font-size:20px;line-height:26px;font-weight:700">{escape(title)}</h1>
{paragraphs}
{button}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:28px 0"><tr><td bgcolor="#eaf4f4" style="padding:18px 20px;background:#eaf4f4;border-left:3px solid #e8bb65;border-radius:3px">
<p style="margin:0 0 8px;color:#292929;font-size:14px;line-height:22px;font-weight:bold">{note_title}</p>
<p style="margin:0;color:#292929;font-size:14px;line-height:22px">{note_body}</p>
</td></tr></table>
{signature}
</td></tr>
<tr><td style="padding:20px 30px;border-top:1px solid #e5e7eb;color:#292929;font-size:12px;line-height:20px">Porto Aurora Talentos · Mensagem automática do sistema.<br>Se você não reconhece esta comunicação, entre em contato com o RH do Porto Aurora.</td></tr>
</table></td></tr></table></body></html>'''


def add_branded_html(message, subject: str, body: str, *, template: str = "default"):
    message.add_alternative(render_email(subject, body, template=template), subtype="html", charset="utf-8")
    message.get_payload()[-1].add_related(
        LOGO_PATH.read_bytes(), maintype="image", subtype="png",
        cid="<porto-aurora-logo>", disposition="inline", filename="porto-aurora-logo.png",
    )
    if template == "rh-welcome":
        from app.services.welcome_email_template import ICONS
        for name, path in ICONS.items():
            message.get_payload()[-1].add_related(path.read_bytes(), maintype="image", subtype="png",
                cid=f"<porto-aurora-{name}>", disposition="inline", filename=f"porto-aurora-{name}.png")
