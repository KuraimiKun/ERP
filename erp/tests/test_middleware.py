"""
Middleware Tests

Tests for TenantMiddleware (tenant routing, approval redirects) and
ERPSetupMiddleware (setup wizard redirect).
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

from tenants.middleware import TenantMiddleware
from erp.middleware import ERPSetupMiddleware

User = get_user_model()


def _dummy_response(request):
    """Minimal get_response callable for middleware."""
    from django.http import HttpResponse

    return HttpResponse("OK")


def _add_session_and_messages(request):
    """Attach session and messages backends to a request (needed for redirects)."""
    SessionMiddleware(_dummy_response).process_request(request)
    MessageMiddleware(_dummy_response).process_request(request)
    request.session.save()


class TestTenantMiddleware(TestCase):
    """Tests for tenant database routing and access control."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(_dummy_response)

    def _make_request(self, path, user=None):
        request = self.factory.get(path)
        request.user = user or AnonymousUser()
        _add_session_and_messages(request)
        return request

    def test_public_urls_pass_through(self):
        """Public URLs should not trigger redirects for anonymous users."""
        for url in ["/admin/", "/accounts/login/", "/static/test.css", "/"]:
            request = self._make_request(url)
            response = self.middleware(request)
            self.assertEqual(response.status_code, 200, f"{url} did not pass through")

    def test_unauthenticated_request_passes_through(self):
        """Anonymous users on non-public paths still get through to the view layer."""
        request = self._make_request("/erp/dashboard/")
        response = self.middleware(request)
        # Middleware passes through; authentication is enforced at the view level
        self.assertEqual(response.status_code, 200)

    @patch("tenants.middleware.clear_current_db_alias")
    @patch("tenants.middleware.set_current_db_alias")
    def test_staff_user_uses_default_database(self, mock_set, mock_clear):
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = True
        user.is_superuser = False

        request = self._make_request("/erp/dashboard/", user=user)
        self.middleware(request)
        mock_set.assert_called_with("default")

    @patch("tenants.middleware.clear_current_db_alias")
    @patch("tenants.middleware.set_current_db_alias")
    def test_superuser_uses_default_database(self, mock_set, mock_clear):
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = False
        user.is_superuser = True

        request = self._make_request("/erp/dashboard/", user=user)
        self.middleware(request)
        mock_set.assert_called_with("default")

    @patch("tenants.middleware.PUBLIC_URLS", ["/admin/", "/accounts/login/", "/static/"])
    def test_pending_user_redirects_to_pending_approval(self):
        """With '/' removed from PUBLIC_URLS, pending users get redirected."""
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = False
        user.is_superuser = False
        user.is_approved = False
        user.approval_status = "pending"

        request = self._make_request("/erp/dashboard/", user=user)
        middleware = TenantMiddleware(_dummy_response)
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("pending", response.url)

    @patch("tenants.middleware.PUBLIC_URLS", ["/admin/", "/accounts/login/", "/static/"])
    def test_rejected_user_redirects_to_rejected(self):
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = False
        user.is_superuser = False
        user.is_approved = False
        user.approval_status = "rejected"

        request = self._make_request("/erp/dashboard/", user=user)
        middleware = TenantMiddleware(_dummy_response)
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("rejected", response.url)

    @patch("tenants.middleware.PUBLIC_URLS", ["/admin/", "/accounts/login/", "/static/"])
    def test_suspended_user_redirects_to_login(self):
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = False
        user.is_superuser = False
        user.is_approved = False
        user.approval_status = "suspended"

        request = self._make_request("/erp/dashboard/", user=user)
        _add_session_and_messages(request)
        middleware = TenantMiddleware(_dummy_response)
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    @patch("tenants.middleware.clear_current_db_alias")
    @patch("tenants.middleware.get_tenant_db_alias", return_value="tenant_42")
    @patch("tenants.middleware.set_current_db_alias")
    def test_approved_user_with_database_sets_alias(self, mock_set, mock_get, mock_clear):
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = False
        user.is_superuser = False
        user.is_approved = True

        request = self._make_request("/erp/dashboard/", user=user)
        self.middleware(request)
        mock_set.assert_called_with("tenant_42")

    @patch("tenants.middleware.PUBLIC_URLS", ["/admin/", "/accounts/login/", "/static/"])
    @patch("tenants.middleware.clear_current_db_alias")
    @patch("tenants.middleware.get_tenant_db_alias", return_value="default")
    def test_approved_user_without_database_redirects(self, mock_get, mock_clear):
        user = MagicMock()
        user.is_authenticated = True
        user.is_staff = False
        user.is_superuser = False
        user.is_approved = True

        request = self._make_request("/erp/dashboard/", user=user)
        middleware = TenantMiddleware(_dummy_response)
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("no-database", response.url)

    @patch("tenants.middleware.clear_current_db_alias")
    def test_clears_context_after_response(self, mock_clear):
        request = self._make_request("/")
        self.middleware(request)
        mock_clear.assert_called()

    def test_kiosk_url_passes_through(self):
        request = self._make_request("/erp/attendance/kiosk/some-uuid/")
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)


class TestERPSetupMiddleware(TestCase):
    """Tests for setup wizard redirect middleware."""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ERPSetupMiddleware(_dummy_response)

    def _make_request(self, path, user=None):
        request = self.factory.get(path)
        request.user = user or AnonymousUser()
        return request

    def test_non_erp_url_passes_through(self):
        request = self._make_request("/admin/")
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_api_url_skips_setup_check(self):
        """API requests should not be redirected to setup wizard."""
        request = self._make_request("/api/v1/departments/")
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_static_url_skips_setup_check(self):
        request = self._make_request("/static/erp.css")
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_setup_url_itself_passes_through(self):
        user = MagicMock()
        user.is_authenticated = True
        user.is_approved = True

        request = self._make_request("/erp/setup/", user=user)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @patch("erp.middleware.is_setup_complete", return_value=True)
    def test_erp_url_with_complete_setup_passes_through(self, mock_setup):
        user = MagicMock()
        user.is_authenticated = True
        user.is_approved = True

        request = self._make_request("/erp/dashboard/", user=user)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    @patch("erp.middleware.is_setup_complete", return_value=False)
    def test_erp_url_with_incomplete_setup_redirects(self, mock_setup):
        user = MagicMock()
        user.is_authenticated = True
        user.is_approved = True

        request = self._make_request("/erp/dashboard/", user=user)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("setup", response.url)

    def test_i18n_prefixed_erp_url_stripped(self):
        """The middleware should strip /en/, /ar/ prefixes before checking."""
        user = MagicMock()
        user.is_authenticated = True
        user.is_approved = True

        # /en/erp/setup/ should match the SKIP_PREFIXES for /erp/setup/
        request = self._make_request("/en/erp/setup/", user=user)
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
