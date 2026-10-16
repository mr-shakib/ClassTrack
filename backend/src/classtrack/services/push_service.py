"""Push notifications to the mobile app, through Firebase Cloud Messaging.

A push is queued on the session and sent only once the caller has committed, as
an email is, so a check that rolls back never buzzes anyone's phone. Unlike an
email, nobody sends it by hand: the commit itself hands the queue to the sender
the app starts (``start``), so a notification raised anywhere -- a request or the
sweep -- reaches the phone. The tests and the command line never start the
sender, so nothing they queue is sent, which matters for the same reason it does
for email: the demo reports real teachers absent.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx
import jwt
from sqlalchemy import delete, event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, SessionTransaction

from classtrack.core.config import get_settings
from classtrack.models import PushDevice, User

logger = logging.getLogger(__name__)

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND = "https://fcm.googleapis.com/v1/projects/{project}/messages:send"

_OUTBOX = "push_outbox"

#: Pushed only, never kept as a notification: it is worth something for minutes.
CLASS_REMINDER = "CLASS_REMINDER"

#: The Android notification channels the app creates (MainActivity.kt), so a
#: teacher can silence reminders and keep the alerts, or the other way round.
CHANNEL_CLASSES = "classes"
CHANNEL_ALERTS = "alerts"

#: Phones sent to at once.
_PARALLEL = 10

#: Errors that mean the phone is gone: the app was removed, or the token was
#: dropped at sign-out, or it belongs to another Firebase project.
_STALE = frozenset({"UNREGISTERED", "SENDER_ID_MISMATCH"})


@dataclass(frozen=True)
class Push:
    user_id: int
    title: str
    body: str
    #: A ``NotificationKind`` value, or ``CLASS_REMINDER``.
    kind: str
    #: The web path it is about, as on the notification. The app opens it on a tap.
    link: str | None = None
    #: Not delivered after this long: a phone that comes back online after the
    #: class has started has no use for "starts in 10 minutes".
    ttl_seconds: int | None = None


def queue(session: AsyncSession | Session, push: Push) -> None:
    """Send ``push`` once the transaction in progress commits; never, if it rolls back."""
    sync = session.sync_session if isinstance(session, AsyncSession) else session
    if not sync.in_transaction():
        # So a rollback before any SQL still discards it. Begins without I/O:
        # the connection is taken at the first statement, as always.
        sync.begin()
    session.info.setdefault(_OUTBOX, []).append(push)


def take(session: AsyncSession | Session) -> list[Push]:
    """Remove and return everything queued on the session."""
    return session.info.pop(_OUTBOX, [])


# --- handing over on commit -----------------------------------------------------

#: Where a commit hands its pushes: the running sender. None outside the app.
_sink: Callable[[list[Push]], None] | None = None


@event.listens_for(Session, "after_commit")
def _hand_over(session: Session) -> None:
    pushes = take(session)
    if pushes and _sink is not None:
        _sink(pushes)


@event.listens_for(Session, "after_soft_rollback")
def _discard(session: Session, previous_transaction: SessionTransaction) -> None:
    # The whole transaction, not a savepoint inside it.
    if previous_transaction.parent is None:
        take(session)


def start() -> asyncio.Task[None] | None:
    """Send every push committed from now on, until the task is cancelled.

    Returns None, and sends nothing, when no service account is configured.
    """
    global _sink
    if not enabled():
        logger.info("Push disabled (CLASSTRACK_FCM_CREDENTIALS unset); in-app only")
        return None
    pending: asyncio.Queue[list[Push]] = asyncio.Queue()
    _sink = pending.put_nowait
    task = asyncio.create_task(_send_forever(pending))
    task.add_done_callback(_stopped)
    return task


def _stopped(_task: asyncio.Task[None]) -> None:
    global _sink
    _sink = None


async def _send_forever(pending: asyncio.Queue[list[Push]]) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            pushes = await pending.get()
            try:
                await send_all(pushes, client=client)
            except Exception:
                # The records they report on are committed, and every push but
                # a class reminder is still in the bell.
                logger.exception("Push batch failed; %d dropped", len(pushes))


# --- sending ----------------------------------------------------------------------


@dataclass(frozen=True)
class _ServiceAccount:
    project_id: str
    client_email: str
    private_key: str
    private_key_id: str | None
    token_uri: str


def enabled() -> bool:
    return _service_account() is not None


def _service_account() -> _ServiceAccount | None:
    return _load(get_settings().fcm_credentials)


@lru_cache
def _load(value: str | None) -> _ServiceAccount | None:
    """The service account, from its JSON or from the file holding it."""
    if not value or not value.strip():
        return None
    text = value.strip()
    try:
        if not text.startswith("{"):
            text = Path(text).read_text()
        raw = json.loads(text)
        return _ServiceAccount(
            project_id=raw["project_id"],
            client_email=raw["client_email"],
            private_key=raw["private_key"],
            private_key_id=raw.get("private_key_id"),
            token_uri=raw.get("token_uri") or "https://oauth2.googleapis.com/token",
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.error("CLASSTRACK_FCM_CREDENTIALS is not a service account (%s); push disabled", exc)
        return None


#: The OAuth access token, and when it expires (``time.monotonic``).
_access: tuple[str, float] | None = None


async def _access_token(
    client: httpx.AsyncClient, account: _ServiceAccount, *, fresh: bool = False
) -> str:
    """Sign in to Google as the service account. Tokens last an hour; reused till near then."""
    global _access
    if not fresh and _access is not None and _access[1] - time.monotonic() > 300:
        return _access[0]
    now = int(time.time())
    assertion = jwt.encode(
        {
            "iss": account.client_email,
            "scope": FCM_SCOPE,
            "aud": account.token_uri,
            "iat": now,
            "exp": now + 3600,
        },
        account.private_key,
        algorithm="RS256",
        headers={"kid": account.private_key_id} if account.private_key_id else None,
    )
    response = await client.post(
        account.token_uri,
        data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
    )
    response.raise_for_status()
    body = response.json()
    _access = (body["access_token"], time.monotonic() + int(body.get("expires_in", 3600)))
    return _access[0]


def _message(push: Push, token: str) -> dict[str, object]:
    android: dict[str, object] = {
        "priority": "high",
        "notification": {
            "channel_id": CHANNEL_CLASSES if push.kind == CLASS_REMINDER else CHANNEL_ALERTS
        },
    }
    apns: dict[str, object] = {"payload": {"aps": {"sound": "default"}}}
    if push.ttl_seconds is not None:
        android["ttl"] = f"{max(push.ttl_seconds, 0)}s"
        apns["headers"] = {"apns-expiration": str(int(time.time()) + max(push.ttl_seconds, 0))}
    return {
        "token": token,
        "notification": {"title": push.title, "body": push.body},
        # Data values must be strings.
        "data": {"kind": push.kind, "link": push.link or ""},
        "android": android,
        "apns": apns,
    }


def _error_code(response: httpx.Response) -> str | None:
    try:
        error = response.json()["error"]
    except (ValueError, KeyError, TypeError):
        return None
    for detail in error.get("details") or []:
        if isinstance(detail, dict) and detail.get("errorCode"):
            return detail["errorCode"]
    return error.get("status")


async def send_all(
    pushes: list[Push],
    *,
    client: httpx.AsyncClient,
    sessions: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Deliver each push to every phone its account has registered.

    A failure is logged, never raised. A phone Firebase no longer knows is
    forgotten, so it is not tried again.
    """
    account = _service_account()
    if account is None or not pushes:
        return
    if sessions is None:
        from classtrack.db.session import get_sessionmaker

        sessions = get_sessionmaker()

    # Read and let go before sending: SQLite would hold writers back for as long
    # as this read stayed open.
    async with sessions() as session:
        rows = (
            await session.execute(
                select(PushDevice.user_id, PushDevice.token)
                .join(User, User.id == PushDevice.user_id)
                .where(PushDevice.user_id.in_({p.user_id for p in pushes}), User.is_active)
            )
        ).all()
    phones: dict[int, list[str]] = {}
    for user_id, token in rows:
        phones.setdefault(user_id, []).append(token)
    if not phones:
        return

    try:
        access = await _access_token(client, account)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("Push sign-in to Google failed; %d not sent: %s", len(pushes), exc)
        return

    url = FCM_SEND.format(project=account.project_id)
    token = {"access": access}
    sent = 0
    stale: set[str] = set()
    # A batch to everyone is hundreds of pushes: phones are sent to side by side,
    # and each phone's pushes in order, stopping at the first that finds it gone.
    gate = asyncio.Semaphore(_PARALLEL)

    async def post(body: dict[str, object]) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token['access']}"}
        response = await client.post(url, json=body, headers=headers)
        if response.status_code == 401:
            # The access token lapsed early; sign in again, once.
            token["access"] = await _access_token(client, account, fresh=True)
            headers = {"Authorization": f"Bearer {token['access']}"}
            response = await client.post(url, json=body, headers=headers)
        return response

    async def to_phone(phone: str, queued: list[Push]) -> None:
        nonlocal sent
        async with gate:
            for push in queued:
                try:
                    response = await post({"message": _message(push, phone)})
                except (httpx.HTTPError, KeyError, ValueError) as exc:
                    logger.warning("Push to user %s failed: %s", push.user_id, exc)
                    continue
                if response.is_success:
                    sent += 1
                    continue
                code = _error_code(response)
                if response.status_code == 404 or code in _STALE:
                    stale.add(phone)
                    return
                logger.warning(
                    "Push to user %s rejected (%s %s): %s",
                    push.user_id,
                    response.status_code,
                    code,
                    response.text[:300],
                )

    by_phone: dict[str, list[Push]] = {}
    for push in pushes:
        for phone in phones.get(push.user_id, []):
            by_phone.setdefault(phone, []).append(push)
    await asyncio.gather(*(to_phone(phone, queued) for phone, queued in by_phone.items()))

    if stale:
        async with sessions() as session:
            await session.execute(delete(PushDevice).where(PushDevice.token.in_(stale)))
            await session.commit()
    logger.info("Pushed %d to %d phones; %d phones forgotten", sent, len(by_phone), len(stale))


# --- the phones ---------------------------------------------------------------------


async def register(session: AsyncSession, *, user: User, token: str, platform: str) -> None:
    """Send this account's pushes to this phone. A phone serves the last to sign in on it."""
    device = await session.scalar(select(PushDevice).where(PushDevice.token == token))
    if device is None:
        session.add(PushDevice(user_id=user.id, token=token, platform=platform))
    else:
        device.user_id = user.id
        device.platform = platform


async def has_phone(session: AsyncSession, user: User) -> bool:
    """Whether some phone gets this account's pushes: the app is in use."""
    found = await session.scalar(
        select(PushDevice.id).where(PushDevice.user_id == user.id).limit(1)
    )
    return found is not None


async def unregister(session: AsyncSession, *, user: User, token: str) -> None:
    """Stop pushing to this phone, if it is this account's."""
    await session.execute(
        delete(PushDevice).where(PushDevice.token == token, PushDevice.user_id == user.id)
    )
