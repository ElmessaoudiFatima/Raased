import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import current_app

logger = logging.getLogger("raased.email")

BRAND = """
<div style="font-family:'Segoe UI',Arial,sans-serif;max-width:560px;margin:0 auto;border:1px solid #e5e9f0;border-radius:16px;overflow:hidden">
  <div style="background:linear-gradient(135deg,#0f1733 0%,#0d7377 100%);padding:24px 32px;color:#fff">
    <span style="font-size:22px;font-weight:800;letter-spacing:.5px">راصد&nbsp;·&nbsp;Raased</span>
  </div>
  <div style="padding:32px">
"""

BRAND_END = """
  </div>
  <div style="padding:16px 32px;background:#f6f8fc;color:#64748b;font-size:12px">
    Cet e-mail est envoyé par la plateforme Raased. Merci de ne pas y répondre.
  </div>
</div>
"""


def _send(to_email: str, subject: str, html: str, plain: str):
    app = current_app._get_current_object()
    html_body = BRAND + html + BRAND_END
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{app.config['EMAIL_FROM_NAME']} <{app.config['EMAIL_FROM']}>"
    msg["To"] = to_email
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    host = app.config["SMTP_HOST"]
    if not host:
        logger.warning("[RAASED] SMTP désactivé (mode dev) — email en console pour %s", to_email)
        logger.warning("[RAASED] Sujet: %s", subject)
        logger.warning("[RAASED] Corps: %s", plain)
        return
    try:
        if app.config["SMTP_USE_TLS"]:
            server = smtplib.SMTP(host, app.config["SMTP_PORT"], timeout=15)
            server.starttls(context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(host, app.config["SMTP_PORT"], timeout=15)
        if app.config["SMTP_USER"]:
            server.login(app.config["SMTP_USER"], app.config["SMTP_PASSWORD"])
        server.sendmail(app.config["EMAIL_FROM"], [to_email], msg.as_string())
        server.quit()
    except Exception as exc:
        logger.error("[RAASED] Échec envoi email à %s: %s", to_email, exc)
        raise


def send_code_email(to_email: str, code: str, first_name: str, purpose: str = "vérification"):
    subject = "Votre code de vérification Raased"
    html = f"""
    <p style="color:#334155;font-size:15px">Bonjour <b>{first_name}</b>,</p>
    <p style="color:#334155;font-size:15px">Utilisez le code ci-dessous pour finaliser la {purpose} de votre compte Raased. Il expire dans 10 minutes.</p>
    <div style="background:#0d7377;color:#fff;font-size:32px;font-weight:800;letter-spacing:8px;text-align:center;padding:18px;border-radius:12px;margin:24px 0">{code}</div>
    <p style="color:#64748b;font-size:13px">Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.</p>
    """
    plain = f"Votre code de vérification Raased est : {code}. Il expire dans 10 minutes."
    _send(to_email, subject, html, plain)


def send_invitation_email(to_email: str, first_name: str, invitation_link: str, org_name: str = None):
    subject = "Votre invitation à rejoindre Raased"
    org_line = (
        f"La société <b>{org_name}</b> vous a invité à rejoindre la plateforme Raased."
        if org_name
        else "Vous avez été invité à rejoindre la plateforme Raased."
    )
    html = f"""
    <p style="color:#334155;font-size:15px">Bonjour <b>{first_name}</b>,</p>
    <p style="color:#334155;font-size:15px">{org_line}</p>
    <p style="color:#334155;font-size:15px">Cliquez sur le bouton ci-dessous pour créer votre mot de passe et activer votre compte. Le lien est valable 48 heures.</p>
    <a href="{invitation_link}" style="display:inline-block;background:#0d7377;color:#fff;font-size:15px;font-weight:700;padding:14px 28px;border-radius:10px;text-decoration:none;margin:20px 0">Créer mon mot de passe</a>
    <p style="color:#64748b;font-size:12px">Lien direct : {invitation_link}</p>
    """
    plain = f"Bonjour {first_name}, {org_line} Cliquez sur ce lien pour créer votre mot de passe (valable 48h) : {invitation_link}"
    _send(to_email, subject, html, plain)