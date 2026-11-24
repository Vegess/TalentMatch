"""Outgoing email over SMTP, sent on a background thread so requests never wait on the mail server.

Without SMTP_HOST configured, messages are written to the server log (useful locally; links included only
when ENV != production)."""
import logging
import smtplib
from concurrent.futures import ThreadPoolExecutor
from email.message import EmailMessage

from app.core import config

log = logging.getLogger("talentmatch.email")
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")
sent_log: list = []  # last messages, for tests / local debugging (never contains secrets in production)


def _send_now(to: str, subject: str, text: str):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.EMAIL_FROM, to, subject
    msg.set_content(text)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20) as s:
            if config.SMTP_TLS:
                s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
    except Exception as e:  # never break the request because email failed
        log.warning("email to %s failed: %s", to, e)


def send(to: str, subject: str, text: str):
    sent_log.append({"to": to, "subject": subject, "text": text})
    del sent_log[:-50]
    if config.SMTP_HOST:
        _pool.submit(_send_now, to, subject, text)
    else:
        print(f"[email] to={to} subject={subject!r}" + ("" if config.IS_PROD else f"\n{text}\n"))


def wrap(name: str, lines: str, link: str | None = None) -> str:
    url = (config.FRONTEND_URL.rstrip("/") + link) if link else None
    return (f"Hi {name.split(' ')[0] if name else 'there'},\n\n{lines}\n\n" + (f"{url}\n\n" if url else "") +
            "— TalentMatch\n\nYou can turn off email notifications in Account settings.")
