from email.message import EmailMessage

from app.services.email_template import add_branded_html, render_email


def test_email_uses_light_brand_layout_with_dark_mode_overrides():
    html = render_email("Access", "https://talentos.example/confirmar#token=abc&purpose=RESET")
    assert 'name="color-scheme" content="light"' in html
    assert 'class="email-card" bgcolor="#ffffff"' in html
    assert 'background-image:linear-gradient(#145c67,#145c67)' in html
    assert '[data-ogsc] .brand-background' in html
    assert 'color:#ffffff;-webkit-text-fill-color:#ffffff' in html
    assert 'background:#262626' not in html


def test_email_escapes_content_and_preserves_confirmation_link():
    url = 'https://talentos.example/confirmar#token=abc&purpose=SETUP'
    html = render_email('<script>title</script>', '<img src=x onerror=alert(1)>\n\n' + url)
    assert '<script>' not in html and '<img src=x' not in html
    assert '&lt;script&gt;' in html and '&lt;img' in html
    assert 'href="https://talentos.example/confirmar#token=abc&amp;purpose=SETUP"' in html
    assert 'Porto Aurora' in html and 'cid:tgpm-logo' not in html


def test_test_message_does_not_instruct_recipient_to_follow_selection():
    html = render_email('Teste de envio do Porto Aurora Talentos', 'Mensagem de teste')
    assert 'Você não precisa realizar nenhuma ação.' in html
    assert 'Acompanhe seu processo' not in html
    assert 'TESTE DE COMUNICAÇÃO' in html


def test_rh_welcome_uses_aurora_identity_and_native_icons_with_plain_text_alternative():
    message = EmailMessage()
    message.set_content("Olá, Pessoa! Seja bem-vinda.")
    add_branded_html(message, "Boas-vindas", "Olá, <Pessoa>!", template="rh-welcome")
    html = message.get_body(preferencelist=("html",)).get_content()
    assert "&lt;Pessoa&gt;" in html and "<Pessoa>" not in html
    assert "atividade pendente" not in html
    assert message.get_body(preferencelist=("plain",))
    assert len([part for part in message.walk() if part.get_content_maintype() == "image"]) == 4
    assert any(part.get("Content-ID") == "<porto-aurora-logo>" for part in message.walk())
    assert "#145c67" in html and "#f3f4f4" in html
    assert "cid:porto-aurora-vacancies" in html and "cid:porto-aurora-people" in html and "cid:porto-aurora-stages" in html
    assert 'width="48" height="48"' in html
    assert "welcome-grid-cell" not in html


def test_default_email_embeds_approved_logo_and_keeps_plain_text():
    message = EmailMessage()
    message.set_content("Confirme seu cadastro.")
    add_branded_html(message, "Confirme seu cadastro", "https://example.test/confirmar#token=teste")
    html = message.get_body(preferencelist=("html",)).get_content()
    assert 'cid:porto-aurora-logo' in html
    assert '#e8bb65' in html and '#eaf4f4' in html
    assert '#d52b32' not in html
    assert message.get_body(preferencelist=("plain",)).get_content().strip() == "Confirme seu cadastro."
    assert any(part.get("Content-ID") == "<porto-aurora-logo>" for part in message.walk())
