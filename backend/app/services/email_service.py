"""
Service d'envoi d'emails.

Configuration via .env :
    SMTP_HOST        - serveur SMTP (ex: smtp.gmail.com)
    SMTP_PORT        - port (587 pour STARTTLS, 465 pour SSL)
    SMTP_USER        - adresse expéditeur
    SMTP_PASSWORD    - mot de passe / App Password
    SMTP_USE_TLS     - true pour STARTTLS (recommandé sur 587)
    EMAIL_FROM_NAME  - nom affiché dans le champ "De"

Si SMTP_HOST n'est pas configuré, les emails sont simplement loggés
(mode dégradé pratique en développement).
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _build_otp_html(otp_code: str, first_name: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px;">
      <div style="max-width:480px; margin:auto; background:#fff; border-radius:8px; padding:32px; box-shadow:0 2px 8px rgba(0,0,0,.1);">
        <h2 style="color:#1a1a2e; margin-bottom:8px;">Vérification de votre email</h2>
        <p style="color:#555;">Bonjour <strong>{first_name}</strong>,</p>
        <p style="color:#555;">Voici votre code de vérification Raased :</p>
        <div style="text-align:center; margin:28px 0;">
          <span style="font-size:36px; font-weight:bold; letter-spacing:12px; color:#3b82f6; background:#eff6ff; padding:16px 24px; border-radius:8px;">
            {otp_code}
          </span>
        </div>
        <p style="color:#888; font-size:13px;">Ce code est valable <strong>10 minutes</strong>.<br>Si vous n'avez pas fait cette demande, ignorez cet email.</p>
        <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
        <p style="color:#aaa; font-size:11px; text-align:center;">© 2026 Raased — Supervision logistique intelligente</p>
      </div>
    </body>
    </html>
    """


def send_otp_email(to_email: str, otp_code: str, first_name: str) -> None:
    """
    Envoie le code OTP par email.
    En mode développement (SMTP_HOST vide), logue simplement le code.
    """
    smtp_host = getattr(settings, "SMTP_HOST", "")
    smtp_user = getattr(settings, "SMTP_USER", "")

    if not smtp_host:
        # Mode développement : affichage dans les logs
        logger.warning(
            "[EMAIL - DEV MODE] OTP pour %s : %s", to_email, otp_code
        )
        return

    smtp_port = int(getattr(settings, "SMTP_PORT", 587))
    smtp_password = getattr(settings, "SMTP_PASSWORD", "")
    use_tls = str(getattr(settings, "SMTP_USE_TLS", "true")).lower() == "true"
    from_name = getattr(settings, "EMAIL_FROM_NAME", "Raased")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Votre code de vérification Raased"
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = to_email

    html_body = _build_otp_html(otp_code, first_name)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)

        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_email], msg.as_string())
        server.quit()
        logger.info("OTP email sent to %s", to_email)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send OTP email to %s: %s", to_email, exc)
        # On ne re-raise pas : l'OTP est en DB, l'appelant peut retenter via /resend-otp


def _build_invitation_html(first_name: str, invitation_link: str, org_name: str | None = None) -> str:
    company_phrase = f"L'entreprise <strong>{org_name}</strong>" if org_name else "Votre entreprise"
    return f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:20px; margin:0;">
      <div style="max-width:480px; margin:auto; background:#fff; border-radius:8px; padding:32px; box-shadow:0 2px 8px rgba(0,0,0,.1);">
        <h2 style="color:#1a1a2e; margin-bottom:8px;">Bienvenue sur Raased</h2>
        <p style="color:#555;">Bonjour <strong>{first_name}</strong>,</p>
        <p style="color:#555;">{company_phrase} vous a créé un compte conducteur sur la plateforme de supervision logistique Raased.</p>
        <p style="color:#555;">Pour activer votre compte et choisir votre mot de passe, cliquez sur le bouton ci-dessous :</p>
        <div style="text-align:center; margin:30px 0;">
          <a href="{invitation_link}" style="background-color:#1e40af; color:#ffffff; padding:14px 28px; text-decoration:none; border-radius:6px; font-weight:bold; display:inline-block; font-size:15px;">
            Définir mon mot de passe
          </a>
        </div>
        <p style="color:#777; font-size:13px; line-height:1.5;">
          Ou copiez ce lien dans votre navigateur :<br>
          <a href="{invitation_link}" style="color:#2563eb; word-break:break-all;">{invitation_link}</a>
        </p>
        <p style="color:#888; font-size:13px; margin-top:20px;">
          Ce lien est valable pendant <strong>48 heures</strong>.<br>
          Si vous n'êtes pas concerné, vous pouvez ignorer cet email.
        </p>
        <hr style="border:none; border-top:1px solid #eee; margin:24px 0;">
        <p style="color:#aaa; font-size:11px; text-align:center;">© 2026 Raased — Supervision logistique intelligente</p>
      </div>
    </body>
    </html>
    """


def send_invitation_email(to_email: str, first_name: str, invitation_link: str, org_name: str | None = None) -> None:
    """
    Envoie le lien d'invitation au conducteur.
    En mode développement (SMTP_HOST vide), logue le lien.
    """
    smtp_host = getattr(settings, "SMTP_HOST", "")
    smtp_user = getattr(settings, "SMTP_USER", "")

    if not smtp_host:
        logger.warning(
            "[EMAIL - DEV MODE] Invitation link pour %s (%s) : %s",
            first_name,
            to_email,
            invitation_link,
        )
        return

    smtp_port = int(getattr(settings, "SMTP_PORT", 587))
    smtp_password = getattr(settings, "SMTP_PASSWORD", "")
    use_tls = str(getattr(settings, "SMTP_USE_TLS", "true")).lower() == "true"
    from_name = getattr(settings, "EMAIL_FROM_NAME", "Raased")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Activation de votre compte conducteur Raased"
    msg["From"] = f"{from_name} <{smtp_user}>"
    msg["To"] = to_email

    html_body = _build_invitation_html(first_name, invitation_link, org_name)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if use_tls:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)

        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, [to_email], msg.as_string())
        server.quit()
        logger.info("Invitation email sent to %s", to_email)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send invitation email to %s: %s", to_email, exc)

