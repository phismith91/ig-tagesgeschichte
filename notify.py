"""E-Mail-Benachrichtigungen für heute.today."""
import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path

from env import load_env_var

logger = logging.getLogger(__name__)


def load_smtp_config(env_path: str = ".env") -> dict | None:
    """Liest SMTP-Konfiguration aus .env. Gibt None zurück, wenn nicht konfiguriert."""
    path = Path(env_path)
    if not path.exists():
        return None

    host = load_env_var("SMTP_HOST", env_path)
    port = load_env_var("SMTP_PORT", env_path)
    user = load_env_var("SMTP_USER", env_path)
    password = load_env_var("SMTP_PASSWORD", env_path)
    from_addr = load_env_var("SMTP_FROM", env_path)
    to_addr = load_env_var("NOTIFY_EMAIL_TO", env_path) or "philippdschmidt@outlook.com"

    if not all([host, port, user, password, from_addr]):
        return None

    try:
        port_int = int(port)
    except ValueError:
        return None

    return {
        "host": host,
        "port": port_int,
        "user": user,
        "password": password,
        "from": from_addr,
        "to": to_addr,
    }


def send_email(subject: str, body: str, config: dict) -> None:
    """Sendet eine E-Mail über SMTP (STARTTLS oder SSL)."""
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config["from"]
    msg["To"] = config["to"]
    msg.set_content(body)

    # Port 465 erwartet SSL/TLS sofort (z. B. Hetzner), Port 587 STARTTLS.
    if config["port"] == 465:
        with smtplib.SMTP_SSL(config["host"], config["port"]) as server:
            server.login(config["user"], config["password"])
            server.send_message(msg)
    else:
        with smtplib.SMTP(config["host"], config["port"]) as server:
            server.starttls()
            server.login(config["user"], config["password"])
            server.send_message(msg)


def notify_post_result(date_str: str, success: bool, **kwargs) -> None:
    """Benachrichtigt über Posting-Erfolg oder -Fehler."""
    config = load_smtp_config()
    if not config:
        logger.warning("notify: SMTP nicht konfiguriert — überspringe E-Mail")
        return

    if success:
        media_id = kwargs.get("media_id", "unbekannt")
        image_count = kwargs.get("image_count", 0)
        subject = f"heute.today — Post {date_str} erfolgreich"
        body = (
            f"Der Post für {date_str} wurde erfolgreich veröffentlicht.\n\n"
            f"Media-ID: {media_id}\n"
            f"Bilder: {image_count}\n"
        )
    else:
        error = kwargs.get("error", "Unbekannter Fehler")
        step = kwargs.get("step", "unbekannter Schritt")
        subject = f"heute.today — Post {date_str} fehlgeschlagen"
        body = (
            f"Der Post für {date_str} ist fehlgeschlagen.\n\n"
            f"Schritt: {step}\n"
            f"Fehler: {error}\n"
        )

    try:
        send_email(subject, body, config)
    except (smtplib.SMTPException, OSError):
        logger.exception("notify: E-Mail konnte nicht gesendet werden")
