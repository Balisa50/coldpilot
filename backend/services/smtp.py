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
        "password": os.getenv("SMTP_APP_PASSWORD", ""),
    }


async def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    body_text: str,
    from_name: str | None = None,
    in_reply_to: str | None = None,
    references: str | None = None,
) -> dict:
    """
    Send an email via SMTP.
    Returns {"success": True} or {"success": False, "error": str, "bounce": bool}.

    Pass ``in_reply_to`` and ``references`` (both the original Message-ID string,
    e.g. "<abc@domain>") to thread follow-ups into the same conversation.
    """
    cfg = _config()
    if not cfg["username"] or not cfg["password"]:
        raise RuntimeError("SMTP credentials not configured")

    from_addr = cfg["username"]
    if from_name:
        from_header = f"{from_name} <{from_addr}>"
    else:
        from_header = from_addr

    domain = cfg["username"].split("@")[-1] if "@" in cfg["username"] else "localhost"
    msg_id = make_msgid(domain=domain)

    msg = MIMEMultipart("alternative")
    msg["From"] = from_header
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Message-ID"] = msg_id

    # Thread follow-ups into the same conversation (RFC 2822)
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = references or in_reply_to

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=cfg["hostname"],
            port=cfg["port"],
            username=cfg["username"],
            password=cfg["password"],
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


async def test_connection() -> dict:
    """Test SMTP connection without sending. Returns {ok, message}."""
    cfg = _config()
    try:
        smtp = aiosmtplib.SMTP(
            hostname=cfg["hostname"],
            port=cfg["port"],
            start_tls=True,
        )
        await smtp.connect()
        await smtp.login(cfg["username"], cfg["password"])
        await smtp.quit()
        return {"ok": True, "message": f"Connected to {cfg['hostname']} as {cfg['username']}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
