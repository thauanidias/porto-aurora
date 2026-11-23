"""Porto Aurora corporate welcome: official logo, petroleum teal and gold, white and neutral grays."""
import re
from html import escape
from pathlib import Path

ICONS = {name: Path(__file__).resolve().parents[1] / "assets" / f"email-{name}.png"
         for name in ("vacancies", "people", "stages")}


def render_welcome(subject: str, body: str) -> str:
    sections = [part.strip() for part in body.replace("\r\n", "\n").split("\n\n") if part.strip()]
    greeting = sections.pop(0) if sections else "Boas-vindas!"
    signature = sections.pop() if sections and sections[-1].startswith("Com carinho,") else "Equipe Porto Aurora Talentos"
    urls = re.findall(r"https?://[^\s<>]+", body)

    def paragraph(value):
        content = escape(value).replace("\n", "<br>")
        return f'<p style="margin:0 0 17px;color:#303336;font-size:15px;line-height:24px">{content}</p>'

    intro = paragraph(sections.pop(0)) if sections else ""
    remaining = "".join(paragraph(part) for part in sections if not part.startswith("Acesse seu painel:"))
    cards = []
    for name, title, description in [("vacancies", "Vagas", "Organize as oportunidades abertas."), ("people", "Candidatos", "Consulte perfis e currículos."), ("stages", "Etapas", "Acompanhe o andamento de cada seleção.")]:
        cards.append(f'<tr><td style="padding:5px 0"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #e0e2e3;border-radius:9px"><tr><td width="56" valign="middle" bgcolor="#f3f4f4" style="width:56px;padding:16px 0 16px 16px;background:#f3f4f4;border-radius:9px 0 0 9px"><img src="cid:porto-aurora-{name}" width="48" height="48" alt="" style="display:block;width:48px;height:48px;border:0"></td><td valign="middle" bgcolor="#f3f4f4" style="padding:16px;background:#f3f4f4;border-radius:0 9px 9px 0"><strong style="display:block;color:#292c2c;font-size:17px;line-height:23px">{title}</strong><span style="display:block;color:#5c6267;font-size:14px;line-height:21px;margin-top:4px">{description}</span></td></tr></table></td></tr>')
    button = ""
    if urls:
        button = f'<table role="presentation" cellspacing="0" cellpadding="0" style="margin:22px 0"><tr><td bgcolor="#145c67" style="background:#145c67;background-image:linear-gradient(#145c67,#145c67);border-radius:6px"><a href="{escape(urls[0], quote=True)}" style="display:inline-block;padding:14px 22px;color:#ffffff;-webkit-text-fill-color:#ffffff;font-size:14px;font-weight:bold;text-decoration:none">Acessar meu painel</a></td></tr></table>'
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><meta name="supported-color-schemes" content="light"><title>{escape(subject)}</title>
<style>:root{{color-scheme:light}}@media(max-width:480px){{.welcome-padding{{padding:24px 20px!important}}}}@media(prefers-color-scheme:dark){{.welcome-white{{background-color:#ffffff!important;color:#303336!important}}}}[data-ogsc] .welcome-white{{background-color:#ffffff!important;color:#303336!important}}</style></head>
<body style="margin:0;padding:0;background:#eeeeef;font-family:Arial,Helvetica,sans-serif"><table role="presentation" width="100%" cellspacing="0" cellpadding="0" bgcolor="#eeeeef"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" class="welcome-white" width="600" cellspacing="0" cellpadding="0" bgcolor="#ffffff" style="width:100%;max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden">
<tr><td bgcolor="#145c67" align="center" style="padding:27px 24px;background:#145c67;background-image:linear-gradient(#145c67,#145c67);border-radius:10px 10px 0 0"><span style="display:inline-block;background:#ffffff;padding:14px 18px;border-radius:8px"><img src="cid:porto-aurora-logo" width="240" alt="Porto Aurora" style="display:block;width:240px;max-width:100%;height:auto;border:0;color:#145c67"></span></td></tr>
<tr><td class="welcome-padding welcome-white" bgcolor="#ffffff" style="padding:30px 30px 14px;background:#ffffff;color:#303336">
<p style="margin:0 0 10px;color:#145c67;font-size:11px;font-weight:bold;letter-spacing:1.6px">PORTO AURORA TALENTOS · BOAS-VINDAS</p>
<h1 style="margin:0 0 14px;color:#292c2c;font-size:27px;line-height:35px">{escape(greeting)}</h1>
{intro}
<p style="margin:20px 0 8px;color:#5c6267;font-size:11px;font-weight:bold;letter-spacing:1px">SEU ESPAÇO NO RH</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:0 0 22px">{''.join(cards)}</table>
{remaining}{button}
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:8px 0 22px"><tr><td style="padding:15px 18px;background:#f3f4f4;border-left:3px solid #145c67"><p style="margin:0;color:#303336;font-size:14px;line-height:22px;font-weight:bold">Que sua jornada seja cheia de boas conexões!</p></td></tr></table>
<p style="margin:0 0 14px;color:#5c6267;font-size:14px;line-height:22px">{escape(signature).replace(chr(10), '<br>')}</p></td></tr>
<tr><td style="padding:18px 30px;border-top:1px solid #e4e5e5;color:#73797d;font-size:11px;line-height:18px">Porto Aurora Talentos · Porto Aurora<br>Mensagem automática da plataforma.</td></tr></table></td></tr></table></body></html>'''
