from app import security


def test_generate_token_unique_and_hash_stable():
    a, b = security.generate_token(), security.generate_token()
    assert a != b and len(a) >= 20
    assert security.hash_token(a) == security.hash_token(a)
    assert security.hash_token(a) != security.hash_token(b)


def test_password_reset_template_renders():
    from app.email.templates import render

    subject, body = render("PASSWORD_RESET", {"reset_url": "https://x/reset?token=t", "deadline": "1小时"})
    assert "密码" in subject
    assert "https://x/reset?token=t" in body


def test_invite_template_renders():
    from app.email.templates import render

    subject, body = render("INVITE_USER", {"company_name": "Acme", "invite_url": "https://x/accept?token=t"})
    assert "Acme" in subject or "Acme" in body
    assert "https://x/accept?token=t" in body
