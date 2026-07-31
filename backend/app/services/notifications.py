from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text
from sqlmodel import Session, select

from ..config import Settings, get_settings
from ..models import (
    JobDiscoveryBetaMember,
    JobNotificationPreference,
    JobRecommendation,
    NotificationDelivery,
    Profile,
    SharedJobCatalog,
)
from ..schemas import NotificationPreferenceOut


QUEUE_NAME = "careerfit_email_notifications"
EMAIL_SCORE_THRESHOLD = 76.0
EMAIL_CONFIDENCE_THRESHOLD = 0.55
MAX_DELIVERY_ATTEMPTS = 5
SENDING_LEASE_SECONDS = 5 * 60
logger = logging.getLogger("careerfit.notifications")


class NotificationDeliveryError(RuntimeError):
    pass


def get_notification_preference(session: Session, user_id: UUID) -> NotificationPreferenceOut:
    eligible = _eligible_member(session, user_id)
    delivery_available = _delivery_available(get_settings())
    preference = session.get(JobNotificationPreference, user_id)
    return NotificationPreferenceOut(
        eligible=eligible,
        delivery_available=delivery_available,
        email_enabled=bool(eligible and delivery_available and preference and preference.email_enabled),
    )


def update_notification_preference(
    session: Session,
    user_id: UUID,
    email_enabled: bool,
) -> NotificationPreferenceOut:
    eligible = _eligible_member(session, user_id)
    delivery_available = _delivery_available(get_settings())
    if email_enabled and not eligible:
        raise ValueError("Email job alerts are limited to the active Israel discovery beta.")
    if email_enabled and not delivery_available:
        raise ValueError("Email job alerts are not configured yet.")
    preference = session.get(JobNotificationPreference, user_id)
    if preference is None:
        preference = JobNotificationPreference(user_id=user_id)
    preference.email_enabled = bool(email_enabled and eligible)
    preference.unsubscribed_at = None if preference.email_enabled else preference.unsubscribed_at
    preference.updated_at = _now()
    session.add(preference)
    session.commit()
    return NotificationPreferenceOut(
        eligible=eligible,
        delivery_available=delivery_available,
        email_enabled=preference.email_enabled,
    )


def queue_recommendation_email(
    session: Session,
    recommendation: JobRecommendation,
) -> NotificationDelivery | None:
    if recommendation.id is None or recommendation.status != "available":
        return None
    if recommendation.score < EMAIL_SCORE_THRESHOLD or recommendation.confidence < EMAIL_CONFIDENCE_THRESHOLD:
        return None
    if not _eligible_member(session, recommendation.user_id):
        return None
    preference = session.get(JobNotificationPreference, recommendation.user_id)
    if preference is None or not preference.email_enabled:
        return None
    existing = session.exec(
        select(NotificationDelivery).where(
            NotificationDelivery.recommendation_id == recommendation.id,
            NotificationDelivery.channel == "email",
        )
    ).first()
    if existing is not None:
        return existing
    delivery = NotificationDelivery(
        user_id=recommendation.user_id,
        recommendation_id=recommendation.id,
        channel="email",
    )
    session.add(delivery)
    session.flush()
    _enqueue_if_supported(session, delivery.id or 0)
    return delivery


def process_one_queued_email(session: Session) -> NotificationDelivery | None:
    if session.get_bind().dialect.name != "postgresql":
        return None
    row = session.exec(
        text("select msg_id, message from pgmq.read(:queue_name, 300, 1)").bindparams(
            queue_name=QUEUE_NAME
        )
    ).first()
    if row is None:
        return None
    try:
        message = row[1] if isinstance(row[1], dict) else json.loads(str(row[1]))
        delivery_id = int(message["delivery_id"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        logger.error("notification_queue_message_invalid msg_id=%s", int(row[0]))
        session.exec(
            text("select pgmq.archive(:queue_name, :msg_id)").bindparams(
                queue_name=QUEUE_NAME,
                msg_id=int(row[0]),
            )
        )
        session.commit()
        return None
    try:
        delivery = deliver_notification(session, delivery_id)
    except ValueError:
        logger.error(
            "notification_queue_delivery_missing msg_id=%s delivery_id=%s",
            int(row[0]),
            delivery_id,
        )
        session.exec(
            text("select pgmq.archive(:queue_name, :msg_id)").bindparams(
                queue_name=QUEUE_NAME,
                msg_id=int(row[0]),
            )
        )
        session.commit()
        return None
    if delivery.status in {"sent", "suppressed"} or delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
        session.exec(
            text("select pgmq.archive(:queue_name, :msg_id)").bindparams(
                queue_name=QUEUE_NAME,
                msg_id=int(row[0]),
            )
        )
        session.commit()
    return delivery


def deliver_notification(
    session: Session,
    delivery_id: int,
    *,
    settings: Settings | None = None,
    email_lookup=None,
    sender=None,
) -> NotificationDelivery:
    settings = settings or get_settings()
    delivery = session.get(NotificationDelivery, delivery_id)
    if delivery is None:
        raise ValueError("Notification delivery not found.")
    if delivery.status == "sent":
        return delivery
    age_seconds = _age_seconds(delivery.updated_at)
    if delivery.status == "sending" and age_seconds < SENDING_LEASE_SECONDS:
        return delivery
    if delivery.attempts >= MAX_DELIVERY_ATTEMPTS:
        delivery.status = "failed"
        delivery.error_code = "MAX_ATTEMPTS"
        delivery.error = "Delivery stopped after repeated failures."
        delivery.updated_at = _now()
        session.add(delivery)
        session.commit()
        session.refresh(delivery)
        return delivery
    if delivery.status == "failed":
        retry_after = min(60 * 60, 30 * (2 ** max(0, delivery.attempts - 1)))
        if age_seconds < retry_after:
            return delivery
    recommendation = session.get(JobRecommendation, delivery.recommendation_id)
    catalog = (
        session.get(SharedJobCatalog, recommendation.catalog_job_id)
        if recommendation is not None
        else None
    )
    preference = session.get(JobNotificationPreference, delivery.user_id)
    if (
        recommendation is None
        or catalog is None
        or not catalog.active
        or recommendation.status != "available"
        or recommendation.score < EMAIL_SCORE_THRESHOLD
        or recommendation.confidence < EMAIL_CONFIDENCE_THRESHOLD
        or not _eligible_member(session, delivery.user_id)
        or not _discovery_enabled(session, delivery.user_id)
        or preference is None
        or not preference.email_enabled
    ):
        delivery.status = "suppressed"
        delivery.updated_at = _now()
        session.add(delivery)
        session.commit()
        session.refresh(delivery)
        return delivery

    delivery.status = "sending"
    delivery.attempts += 1
    delivery.updated_at = _now()
    session.add(delivery)
    session.commit()
    try:
        lookup = email_lookup or _supabase_auth_email
        send = sender or _send_resend
        recipient = lookup(delivery.user_id, settings)
        unsubscribe_url = _unsubscribe_url(delivery.user_id, settings)
        provider_id = send(
            recipient=recipient,
            catalog=catalog,
            recommendation=recommendation,
            delivery_id=delivery.id or 0,
            unsubscribe_url=unsubscribe_url,
            settings=settings,
        )
        delivery.status = "sent"
        delivery.provider_message_id = provider_id[:300]
        delivery.error_code = ""
        delivery.error = ""
        delivery.sent_at = _now()
    except Exception as exc:
        logger.exception(
            "notification_delivery_failed delivery_id=%s attempt=%s error_code=%s",
            delivery.id or 0,
            delivery.attempts,
            type(exc).__name__[:100],
        )
        delivery.status = "failed"
        delivery.error_code = type(exc).__name__[:100]
        delivery.error = "Email delivery failed and will be retried safely."
    delivery.updated_at = _now()
    session.add(delivery)
    session.commit()
    session.refresh(delivery)
    return delivery


def unsubscribe_email(session: Session, token: str, *, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    user_id = _verify_unsubscribe_token(token, settings)
    if user_id is None:
        return False
    preference = session.get(JobNotificationPreference, user_id)
    if preference is None:
        preference = JobNotificationPreference(user_id=user_id)
    preference.email_enabled = False
    preference.unsubscribed_at = _now()
    preference.updated_at = _now()
    session.add(preference)
    session.commit()
    return True


def _eligible_member(session: Session, user_id: UUID) -> bool:
    return session.exec(
        select(JobDiscoveryBetaMember.user_id).where(
            JobDiscoveryBetaMember.user_id == user_id,
            JobDiscoveryBetaMember.market_code == "IL",
            JobDiscoveryBetaMember.active.is_(True),
        )
    ).first() is not None


def _discovery_enabled(session: Session, user_id: UUID) -> bool:
    return session.exec(
        select(Profile.id).where(
            Profile.user_id == user_id,
            Profile.status == "ready",
            Profile.onboarding_completed.is_(True),
            Profile.recommendations_enabled.is_(True),
        )
    ).first() is not None


def _delivery_available(settings: Settings) -> bool:
    return bool(
        settings.resend_api_key
        and settings.notification_from_email
        and settings.notification_signing_secret
        and settings.public_api_url
    )


def _enqueue_if_supported(session: Session, delivery_id: int) -> None:
    if session.get_bind().dialect.name != "postgresql":
        return
    payload = json.dumps({"delivery_id": delivery_id})
    session.exec(
        text("select * from pgmq.send(:queue_name, cast(:payload as jsonb))").bindparams(
            queue_name=QUEUE_NAME,
            payload=payload,
        )
    )
    session.flush()


def _supabase_auth_email(user_id: UUID, settings: Settings) -> str:
    if not settings.supabase_url or not settings.supabase_secret_key:
        raise NotificationDeliveryError("Supabase email lookup is not configured.")
    endpoint = f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user_id}"
    request = urllib.request.Request(
        endpoint,
        headers={
            "Authorization": f"Bearer {settings.supabase_secret_key}",
            "apikey": settings.supabase_secret_key,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise NotificationDeliveryError("Verified account email could not be resolved.") from exc
    email = str(payload.get("email") or "").strip()
    confirmed = payload.get("email_confirmed_at") or payload.get("confirmed_at")
    if "@" not in email or not confirmed:
        raise NotificationDeliveryError("The account does not have a verified email destination.")
    return email


def _send_resend(
    *,
    recipient: str,
    catalog: SharedJobCatalog,
    recommendation: JobRecommendation,
    delivery_id: int,
    unsubscribe_url: str,
    settings: Settings,
) -> str:
    if not settings.resend_api_key or not settings.notification_from_email:
        raise NotificationDeliveryError("Email delivery is not configured.")
    job_url = catalog.application_link or catalog.source_url
    safe_role = html.escape(catalog.role)
    safe_company = html.escape(catalog.company)
    safe_location = html.escape(catalog.location)
    safe_job_url = html.escape(job_url, quote=True)
    safe_unsubscribe_url = html.escape(unsubscribe_url, quote=True)
    score = round(recommendation.score)
    payload = {
        "from": settings.notification_from_email,
        "to": [recipient],
        "subject": f"New {score}% CareerFit match: {catalog.role}",
        "html": (
            "<h1>A strong new role matched your profile</h1>"
            f"<p><strong>{safe_role}</strong> at {safe_company}"
            f"{f' · {safe_location}' if safe_location else ''}</p>"
            f"<p>CareerFit score: <strong>{score}%</strong>. Your verified profile aligns with the role's key requirements.</p>"
            f"<p><a href=\"{safe_job_url}\">Review the job</a> or "
            f"<a href=\"{html.escape(settings.frontend_url, quote=True)}\">open CareerFit</a>.</p>"
            f"<p style=\"font-size:12px;color:#666\"><a href=\"{safe_unsubscribe_url}\">Manage or stop job emails</a>.</p>"
        ),
        "text": (
            f"A strong new role matched your CareerFit profile.\n\n"
            f"{catalog.role} at {catalog.company}\n"
            f"CareerFit score: {score}%\n"
            f"Review: {job_url}\n\n"
            f"Stop job emails: {unsubscribe_url}"
        ),
        "headers": {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        },
    }
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"careerfit-notification-{delivery_id}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise NotificationDeliveryError("Email provider rejected the delivery.") from exc
    provider_id = str(body.get("id") or "")
    if not provider_id:
        raise NotificationDeliveryError("Email provider did not return a delivery ID.")
    return provider_id


def _unsubscribe_url(user_id: UUID, settings: Settings) -> str:
    token = _unsubscribe_token(user_id, settings)
    return f"{settings.public_api_url}/api/notifications/unsubscribe?{urllib.parse.urlencode({'token': token})}"


def _unsubscribe_token(user_id: UUID, settings: Settings) -> str:
    secret = settings.notification_signing_secret
    if not secret:
        raise NotificationDeliveryError("Notification signing is not configured.")
    payload = str(user_id)
    signature = hmac.new(secret.encode("utf-8"), payload.encode("ascii"), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{payload}.{encoded}"


def _verify_unsubscribe_token(token: str, settings: Settings) -> UUID | None:
    if not settings.notification_signing_secret:
        return None
    try:
        user_text, supplied = token.split(".", 1)
        user_id = UUID(user_text)
    except (ValueError, AttributeError):
        return None
    expected = _unsubscribe_token(user_id, settings).split(".", 1)[1]
    return user_id if hmac.compare_digest(supplied, expected) else None


def _safe_error(exc: Exception) -> str:
    message = " ".join(str(exc).split())
    return (message or type(exc).__name__)[:300]


def _age_seconds(value: datetime) -> float:
    timestamp = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return max(0.0, (_now() - timestamp).total_seconds())


def _now() -> datetime:
    return datetime.now(timezone.utc)
