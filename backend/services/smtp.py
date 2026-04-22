"""
SMTP email sending via aiosmtplib.
Uses Gmail app passwords — simpler than OAuth.
"""
from __future__ import annotations

import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid

import aiosmtplib


def _config() -> dict:
    return {
        "hostname": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "username": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_APP_PASSWORD") or os.getenv("SMTP_PASS", ""),
    }


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str,
    from_name: str | None = None,
    list_unsubscribe: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
) -> dict:
    """
    Send an email via SMTP.
    Returns {"success": True} or {"success": False, "error": str, "bounce": bool}.

    Pass ``in_reply_to`` and ``references`` (both the original Message-ID string,
    e.g. "<abc@domain>") to thread follow-ups into the same conversation.
    """
    cfg = _config()
    username = smtp_user or cfg["username"]
    password = smtp_password or cfg["password"]
    hostname = smtp_host or cfg["hostname"]
    port = smtp_port or cfg["port"]

    if not username or not password:
        raise RuntimeError("SMTP credentials not configured")

    from_addr = username
    if from_name:
        from_header = f"{from_name} <{from_addr}>"
    else:
        from_header = from_addr

    domain = username.split("@")[-1] if "@" in username else "localhost"
    msg_id = make_msgid(domain=domain)

    msg = MIMEMultipart("alternative")
    msg["From"] = from_header
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Message-ID"] = msg_id

    # List-Unsubscribe — required by Gmail/Yahoo 2024 for bulk senders.
    # Without this, cold emails are far more likely to land in spam.
    if list_unsubscribe:
        msg["List-Unsubscribe"] = f"<{list_unsubscribe}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    # Thread follow-ups into the same conversation (RFC 2822)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references or in_reply_to

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=hostname,
            port=port,
            username=username,
            password=password,
            start_tls=True,
        )
        return {"success": True, "message_id": msg_id}
    except aiosmtplib.SMTPResponseException as e:
        # 5xx = permanent failure (bounce)
        is_bounce = 500 <= e.code < 600
        return {
            "success": False,
            "error": f"SMTP {e.code}: {e.message}",
            "bounce": is_bounce,
        }
    except Exception as e:
        return {"success": False, "error": str(e), "bounce": False}


async def test_connection(
    smtp_user: str | None = None,
    smtp_password: str | None = None,
    smtp_host: str | None = None,
    smtp_port: int | None = None,
) -> dict:
    """Test SMTP connection without sending. Returns {ok, message}."""
    cfg = _config()
    username = smtp_user or cfg["username"]
    password = smtp_password or cfg["password"]
    hostname = smtp_host or cfg["hostname"]
    port = smtp_port or cfg["port"]

    try:
        smtp = aiosmtplib.SMTP(
            hostname=hostname,
            port=port,
            start_tls=True,
        )
        await smtp.connect()
        await smtp.login(username, password)
        await smtp.quit()
        return {"ok": True, "message": f"Connected to {hostname} as {username}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
