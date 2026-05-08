import html
import os
import smtplib
from email.message import EmailMessage
from smtplib import SMTPAuthenticationError
from typing import Any, Dict, List

from config import (
    MORNING_BRIEF_FROM_EMAIL,
    MORNING_BRIEF_SUBJECT_PREFIX,
    MORNING_BRIEF_TO_EMAIL,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_USE_SSL,
    SMTP_USE_TLS,
)


class EmailConfigurationError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.lower() in ("1", "true", "yes")


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return int(default)
    return int(value)


def _email_settings() -> Dict[str, Any]:
    username = _env("SMTP_USERNAME", SMTP_USERNAME)
    from_email = _env("MORNING_BRIEF_FROM_EMAIL", MORNING_BRIEF_FROM_EMAIL) or username
    return {
        "host": _env("SMTP_HOST", SMTP_HOST),
        "port": _env_int("SMTP_PORT", SMTP_PORT),
        "username": username,
        "password": _env("SMTP_PASSWORD", SMTP_PASSWORD),
        "use_tls": _env_bool("SMTP_USE_TLS", SMTP_USE_TLS),
        "use_ssl": _env_bool("SMTP_USE_SSL", SMTP_USE_SSL),
        "from_email": from_email,
        "to_email": _env("MORNING_BRIEF_TO_EMAIL", MORNING_BRIEF_TO_EMAIL),
        "subject_prefix": _env(
            "MORNING_BRIEF_SUBJECT_PREFIX", MORNING_BRIEF_SUBJECT_PREFIX
        ),
    }


def _required_setting(settings: Dict[str, Any], key: str) -> str:
    value = settings.get(key, "")
    if not value:
        if key == "from_email":
            raise EmailConfigurationError(
                "Email sender is not configured. Set MORNING_BRIEF_FROM_EMAIL "
                "or SMTP_USERNAME before running a real send."
            )
        if key == "to_email":
            raise EmailConfigurationError(
                "Email recipient is not configured. Set MORNING_BRIEF_TO_EMAIL "
                "before running a real send."
            )
        if key == "host":
            raise EmailConfigurationError(
                "SMTP host is not configured. Set SMTP_HOST before running a real send."
            )
        raise EmailConfigurationError(f"{key} is required for email delivery.")
    return str(value)


def validate_email_settings() -> Dict[str, Any]:
    settings = _email_settings()
    _required_setting(settings, "host")
    _required_setting(settings, "from_email")
    _required_setting(settings, "to_email")
    if not settings["username"]:
        raise EmailConfigurationError(
            "SMTP username is not configured. Set SMTP_USERNAME before running a real send."
        )
    if not settings["password"]:
        raise EmailConfigurationError(
            "SMTP password is not configured. Set SMTP_PASSWORD to your email app password."
        )
    return {
        "status": "configured",
        "host": settings["host"],
        "port": settings["port"],
        "from": settings["from_email"],
        "to": settings["to_email"],
        "use_tls": settings["use_tls"],
        "use_ssl": settings["use_ssl"],
    }


def _item_text(item: Any) -> str:
    if isinstance(item, dict):
        parts = []
        source = item.get("source")
        title = item.get("title")
        summary = item.get("summary")
        link = item.get("link")
        tags = [
            item.get("category"),
            item.get("matched_interest"),
            item.get("matched_ticker"),
            item.get("impact_area"),
        ]
        tag_text = ", ".join(tag for tag in tags if tag)
        heading = " - ".join(part for part in (source, title) if part)
        if heading:
            parts.append(heading)
        if tag_text:
            parts.append(f"Tags: {tag_text}")
        if summary:
            parts.append(summary)
        if link:
            parts.append(f"Read more: {link}")
        return "\n".join(parts)
    return str(item)


def _item_html(item: Any) -> str:
    if isinstance(item, dict):
        source = html.escape(str(item.get("source", "")))
        title = html.escape(str(item.get("title", "")))
        summary = html.escape(str(item.get("summary", "")))
        link = html.escape(str(item.get("link", "")))
        tags = [
            item.get("category"),
            item.get("matched_interest"),
            item.get("matched_ticker"),
            item.get("impact_area"),
        ]
        tag_html = " ".join(
            f"<span>{html.escape(str(tag))}</span>" for tag in tags if tag
        )
        read_more = (
            f'<p><a href="{link}" target="_blank" rel="noopener noreferrer">Read more</a></p>'
            if link
            else ""
        )
        return f"""
        <li>
          <div class="source">{source}</div>
          <strong>{title}</strong>
          <div class="tags">{tag_html}</div>
          <p>{summary}</p>
          {read_more}
        </li>
        """
    return f"<li>{html.escape(str(item))}</li>"


def _section_items(items: List[Any]) -> List[Any]:
    return items if isinstance(items, list) else []


def render_morning_brief_text(brief: Dict[str, Any]) -> str:
    lines = [f"Morning brief for {brief.get('date', '')}", ""]
    for section in ("news", "sports", "finance"):
        lines.append(section.title())
        lines.append("=" * len(section))
        for item in _section_items(brief.get(section, [])):
            lines.append(_item_text(item))
            lines.append("")
    return "\n".join(lines).strip()


def render_morning_brief_html(brief: Dict[str, Any]) -> str:
    sections = []
    for section in ("news", "sports", "finance"):
        items = "\n".join(_item_html(item) for item in _section_items(brief.get(section, [])))
        sections.append(f"<h2>{section.title()}</h2><ul>{items}</ul>")

    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <style>
          body {{ color: #18202a; font-family: Arial, Helvetica, sans-serif; }}
          h1 {{ margin-bottom: 8px; }}
          h2 {{ margin-top: 24px; }}
          ul {{ padding-left: 20px; }}
          li {{ margin-bottom: 18px; }}
          .source {{ color: #586574; font-size: 12px; font-weight: 700; text-transform: uppercase; }}
          .tags span {{ display: inline-block; margin: 6px 6px 0 0; padding: 3px 7px; border: 1px solid #cdd6e1; border-radius: 999px; background: #eef3f8; font-size: 12px; }}
          a {{ color: #174a7c; font-weight: 700; }}
        </style>
      </head>
      <body>
        <h1>Morning Brief</h1>
        <p>{html.escape(str(brief.get("date", "")))}</p>
        {''.join(sections)}
      </body>
    </html>
    """


def build_morning_brief_message(brief: Dict[str, Any]) -> EmailMessage:
    settings = _email_settings()
    from_email = _required_setting(settings, "from_email")
    to_email = _required_setting(settings, "to_email")
    subject_prefix = settings["subject_prefix"]

    message = EmailMessage()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = f"{subject_prefix}: Morning Brief {brief.get('date', '')}"
    message.set_content(render_morning_brief_text(brief))
    message.add_alternative(render_morning_brief_html(brief), subtype="html")
    return message


def send_message(message: EmailMessage) -> Dict[str, Any]:
    settings = _email_settings()
    host = _required_setting(settings, "host")
    from_email = _required_setting(settings, "from_email")
    to_email = _required_setting(settings, "to_email")
    username = settings["username"]
    password = settings["password"]

    smtp_class = smtplib.SMTP_SSL if settings["use_ssl"] else smtplib.SMTP
    with smtp_class(host, settings["port"], timeout=30) as smtp:
        if settings["use_tls"] and not settings["use_ssl"]:
            smtp.starttls()
        if username or password:
            try:
                smtp.login(username, password)
            except SMTPAuthenticationError as exc:
                raise EmailConfigurationError(
                    "SMTP authentication failed. If you are using Gmail, "
                    "enable 2-Step Verification and use a Google App Password "
                    "for SMTP_PASSWORD, not your normal account password."
                ) from exc
        smtp.send_message(message)

    return {
        "status": "sent",
        "from": from_email,
        "to": to_email,
        "subject": message["Subject"],
    }


def send_morning_brief_email(brief: Dict[str, Any]) -> Dict[str, Any]:
    message = build_morning_brief_message(brief)
    return send_message(message)
