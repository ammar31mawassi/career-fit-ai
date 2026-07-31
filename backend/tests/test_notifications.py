from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models import (
    JobDiscoveryBetaMember,
    JobNotificationPreference,
    JobRecommendation,
    NotificationDelivery,
    Profile,
    SharedJobCatalog,
)
from app.services.notifications import (
    deliver_notification,
    queue_recommendation_email,
    unsubscribe_email,
)


USER = UUID("00000000-0000-0000-0000-000000000401")


def _engine():
    return create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)


def test_email_queue_requires_cohort_consent_and_is_idempotent():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        catalog = SharedJobCatalog(content_hash="one", source_name="goozali", external_id="rec-one")
        session.add(catalog)
        session.add(JobDiscoveryBetaMember(user_id=USER, market_code="IL", active=True))
        session.add(JobNotificationPreference(user_id=USER, email_enabled=True))
        session.add(Profile(
            user_id=USER,
            status="ready",
            onboarding_completed=True,
            recommendations_enabled=True,
        ))
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=USER,
            catalog_job_id=catalog.id or 0,
            score=88,
            fit_level="Strong",
            confidence=0.8,
            model_version="fit-test",
            status="available",
        )
        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)

        first = queue_recommendation_email(session, recommendation)
        session.commit()
        second = queue_recommendation_email(session, recommendation)
        deliveries = list(session.exec(select(NotificationDelivery)).all())

    assert first is not None and second is not None
    assert first.id == second.id
    assert len(deliveries) == 1


def test_delivery_sends_once_and_unsubscribe_preserves_auditable_consent_state():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    settings = SimpleNamespace(
        notification_signing_secret="test-signing-secret",
        public_api_url="https://api.example.com",
    )
    sent: list[dict] = []

    def sender(**kwargs):
        sent.append(kwargs)
        return "provider-message-1"

    with Session(engine) as session:
        catalog = SharedJobCatalog(
            content_hash="two",
            source_name="goozali",
            external_id="rec-two",
            company="Example",
            role="Backend Engineer",
            source_url="https://goozali.com/#jobopenings",
        )
        session.add(catalog)
        session.add(JobDiscoveryBetaMember(user_id=USER, market_code="IL", active=True))
        session.add(JobNotificationPreference(user_id=USER, email_enabled=True))
        session.add(Profile(
            user_id=USER,
            status="ready",
            onboarding_completed=True,
            recommendations_enabled=True,
        ))
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=USER,
            catalog_job_id=catalog.id or 0,
            score=88,
            fit_level="Strong",
            confidence=0.8,
            model_version="fit-test",
            status="available",
        )
        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)
        delivery = queue_recommendation_email(session, recommendation)
        session.commit()
        assert delivery is not None and delivery.id is not None

        delivered = deliver_notification(
            session,
            delivery.id,
            settings=settings,
            email_lookup=lambda _user_id, _settings: "candidate@example.com",
            sender=sender,
        )
        repeated = deliver_notification(
            session,
            delivery.id,
            settings=settings,
            email_lookup=lambda _user_id, _settings: "candidate@example.com",
            sender=sender,
        )
        delivered_status = delivered.status
        repeated_status = repeated.status
        token = sent[0]["unsubscribe_url"].split("token=", 1)[1]
        assert unsubscribe_email(session, token, settings=settings)
        preference = session.get(JobNotificationPreference, USER)

    assert delivered_status == "sent"
    assert repeated_status == "sent"
    assert len(sent) == 1
    assert preference is not None and not preference.email_enabled
    assert preference.unsubscribed_at is not None


def test_paused_discovery_suppresses_a_queued_email_before_provider_call():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    settings = SimpleNamespace(
        notification_signing_secret="test-signing-secret",
        public_api_url="https://api.example.com",
    )
    with Session(engine) as session:
        catalog = SharedJobCatalog(content_hash="paused", active=True)
        session.add(catalog)
        session.add(JobDiscoveryBetaMember(user_id=USER, market_code="IL", active=True))
        session.add(JobNotificationPreference(user_id=USER, email_enabled=True))
        session.add(Profile(
            user_id=USER,
            status="ready",
            onboarding_completed=True,
            recommendations_enabled=False,
        ))
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=USER,
            catalog_job_id=catalog.id or 0,
            score=90,
            confidence=0.9,
            status="available",
        )
        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)
        delivery = NotificationDelivery(
            user_id=USER,
            recommendation_id=recommendation.id or 0,
        )
        session.add(delivery)
        session.commit()
        session.refresh(delivery)
        called = False

        def sender(**_kwargs):
            nonlocal called
            called = True
            return "unexpected"

        result = deliver_notification(
            session,
            delivery.id or 0,
            settings=settings,
            email_lookup=lambda *_args: "candidate@example.com",
            sender=sender,
        )

    assert result.status == "suppressed"
    assert not called


def test_delivery_stops_before_a_sixth_provider_attempt():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    settings = SimpleNamespace(
        notification_signing_secret="test-signing-secret",
        public_api_url="https://api.example.com",
    )
    with Session(engine) as session:
        delivery = NotificationDelivery(
            user_id=USER,
            recommendation_id=123,
            status="failed",
            attempts=5,
        )
        session.add(delivery)
        session.commit()
        session.refresh(delivery)
        called = False

        def sender(**_kwargs):
            nonlocal called
            called = True
            return "unexpected"

        result = deliver_notification(
            session,
            delivery.id or 0,
            settings=settings,
            email_lookup=lambda *_args: "candidate@example.com",
            sender=sender,
        )

    assert result.status == "failed"
    assert result.error_code == "MAX_ATTEMPTS"
    assert not called


def test_email_below_high_confidence_threshold_is_not_queued():
    engine = _engine()
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        catalog = SharedJobCatalog(content_hash="three", source_name="goozali", external_id="rec-three")
        session.add(catalog)
        session.add(JobDiscoveryBetaMember(user_id=USER, market_code="IL", active=True))
        session.add(JobNotificationPreference(user_id=USER, email_enabled=True))
        session.commit()
        session.refresh(catalog)
        recommendation = JobRecommendation(
            user_id=USER,
            catalog_job_id=catalog.id or 0,
            score=70,
            fit_level="Medium",
            confidence=0.7,
            model_version="fit-test",
            status="available",
        )
        session.add(recommendation)
        session.commit()
        session.refresh(recommendation)

        assert queue_recommendation_email(session, recommendation) is None
