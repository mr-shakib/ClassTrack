"""Outbound email, sent through Resend.

A message is queued on the session and sent only once the caller has committed,
so a check that rolls back never mails anyone. Only the request path sends: the
demo seed and the tests run through the same services and queue the same
messages, but never send them -- which matters, because the faculty directory
holds real addresses.
"""

from __future__ import annotations

import html
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from classtrack.core.config import get_settings

logger = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"

_OUTBOX = "email_outbox"

#: Closes every message. The name links to the site in the HTML part.
FOOTER_NAME = "Shakib Howlader"
FOOTER_URL = "https://shakibhowlader.online"


@dataclass(frozen=True)
class Email:
    to: str
    subject: str
    #: Plain text. A blank line separates paragraphs.
    body: str
    link: str | None = None
    link_label: str | None = None


def queue(session: AsyncSession, email: Email) -> None:
    session.info.setdefault(_OUTBOX, []).append(email)


def take(session: AsyncSession) -> list[Email]:
    """Remove and return everything queued on the session. Call after commit."""
    return session.info.pop(_OUTBOX, [])


def _text(email: Email) -> str:
    text = email.body
    if email.link is not None:
        text += f"\n\n{email.link_label or 'Open ClassTrack'}: {email.link}"
    return f"{text}\n\n--\nDeveloped by {FOOTER_NAME}\n{FOOTER_URL}"


def _html(email: Email) -> str:
    paragraphs = "".join(
        f'<p style="margin:0 0 16px">{html.escape(p)}</p>' for p in email.body.split("\n\n")
    )
    button = ""
    if email.link is not None:
        button = (
            f'<p style="margin:24px 0 0"><a href="{html.escape(email.link, quote=True)}" '
            'style="background:#1d4ed8;color:#ffffff;padding:10px 18px;'
            'border-radius:6px;text-decoration:none;display:inline-block">'
            f"{html.escape(email.link_label or 'Open ClassTrack')}</a></p>"
        )
    footer = (
        '<p style="margin:32px 0 0;padding-top:12px;border-top:1px solid #e5e7eb;'
        f'font-size:12px;color:#6b7280">Developed by <a href="{FOOTER_URL}" '
        f'style="color:#6b7280">{html.escape(FOOTER_NAME)}</a></p>'
    )
    return (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'font-size:15px;line-height:1.5;color:#111827;max-width:560px">'
        f"{paragraphs}{button}{footer}</div>"
    )


async def send_all(
    emails: list[Email], *, transport: httpx.AsyncBaseTransport | None = None
) -> None:
    """Deliver each message. A failure is logged, never raised.

    This runs after the response has gone back to the staff member, and the
    record it reports on is already committed, so there is nobody to raise to.
    """
    if not emails:
        return
    settings = get_settings()
    if not settings.resend_api_key:
        logger.info("Email disabled (CLASSTRACK_RESEND_API_KEY unset); %d not sent", len(emails))
        return

    async with httpx.AsyncClient(
        transport=transport,
        timeout=10,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
    ) as client:
        for email in emails:
            try:
                response = await client.post(
                    RESEND_URL,
                    json={
                        "from": settings.email_from,
                        "to": [email.to],
                        "subject": email.subject,
                        "text": _text(email),
                        "html": _html(email),
                    },
                )
            except httpx.HTTPError as exc:
                logger.warning("Email to %s failed: %s", email.to, exc)
                continue
            if response.is_success:
                logger.info("Emailed %s: %s", email.to, email.subject)
            else:
                logger.warning(
                    "Email to %s rejected (%s): %s",
                    email.to,
                    response.status_code,
                    response.text[:300],
                )
