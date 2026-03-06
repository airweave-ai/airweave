"""Unit tests for _create_email_service and _create_user_service factory functions.

Verifies that the factory selects the correct adapter based on settings.
"""

from unittest.mock import MagicMock, patch

from airweave.core.container.factory import _create_email_service, _create_user_service


# ---------------------------------------------------------------------------
# _create_email_service
# ---------------------------------------------------------------------------


class TestCreateEmailServiceResend:
    def test_returns_resend_when_configured(self):
        settings = MagicMock()
        settings.RESEND_API_KEY = "re_test_123"
        settings.RESEND_FROM_EMAIL = "noreply@example.com"

        svc = _create_email_service(settings)

        from airweave.adapters.email.resend import ResendEmailService

        assert isinstance(svc, ResendEmailService)


class TestCreateEmailServiceNull:
    def test_returns_null_when_no_api_key(self):
        settings = MagicMock()
        settings.RESEND_API_KEY = None
        settings.RESEND_FROM_EMAIL = None

        svc = _create_email_service(settings)

        from airweave.adapters.email.null import NullEmailService

        assert isinstance(svc, NullEmailService)

    def test_returns_null_when_no_from_email(self):
        settings = MagicMock()
        settings.RESEND_API_KEY = "re_test_123"
        settings.RESEND_FROM_EMAIL = None

        svc = _create_email_service(settings)

        from airweave.adapters.email.null import NullEmailService

        assert isinstance(svc, NullEmailService)

    def test_returns_null_when_empty_api_key(self):
        settings = MagicMock()
        settings.RESEND_API_KEY = ""
        settings.RESEND_FROM_EMAIL = "noreply@example.com"

        svc = _create_email_service(settings)

        from airweave.adapters.email.null import NullEmailService

        assert isinstance(svc, NullEmailService)


# ---------------------------------------------------------------------------
# _create_user_service
# ---------------------------------------------------------------------------


class TestCreateUserService:
    def test_returns_user_service_instance(self):
        with patch("airweave.domains.users.service.crud"):
            svc = _create_user_service(
                org_service=MagicMock(),
                user_org_repo=MagicMock(),
                email_service=MagicMock(),
            )

        from airweave.domains.users.service import UserService

        assert isinstance(svc, UserService)

    def test_injects_email_service(self):
        email_mock = MagicMock()

        with patch("airweave.domains.users.service.crud"):
            svc = _create_user_service(
                org_service=MagicMock(),
                user_org_repo=MagicMock(),
                email_service=email_mock,
            )

        assert svc._email is email_mock
