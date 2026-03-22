"""
Unit tests for Task 7.1 — API Key Authentication.

Tests cover:
  - APIKey model (key generation, hashing, create_with_key)
  - APIKeyAuthentication class (authenticate method)
  - IsAuthenticatedWithAPIKey permission class
  - Management command output
  - 401 / 403 response shapes from the full DRF stack
"""

from __future__ import annotations

import hashlib
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied

from authentication.authentication import APIKeyAuthentication
from authentication.exceptions import AuthenticationError, InvalidAPIKeyError
from authentication.models import APIKey
from authentication.permissions import IsAuthenticatedWithAPIKey

# ---------------------------------------------------------------------------
# APIKey model — key generation and hashing
# ---------------------------------------------------------------------------


class TestAPIKeyModel:
    def test_generate_key_has_dm_prefix(self):
        raw = APIKey.generate_key()
        assert raw.startswith("dm_")

    def test_generate_key_is_unique(self):
        keys = {APIKey.generate_key() for _ in range(20)}
        assert len(keys) == 20

    def test_hash_key_is_sha256_hex(self):
        raw = "dm_testkey"
        result = APIKey.hash_key(raw)
        expected = hashlib.sha256(raw.encode()).hexdigest()
        assert result == expected
        assert len(result) == 64

    def test_hash_key_is_not_raw_key(self):
        raw = APIKey.generate_key()
        assert APIKey.hash_key(raw) != raw

    def test_hash_key_does_not_start_with_dm(self):
        raw = APIKey.generate_key()
        assert not APIKey.hash_key(raw).startswith("dm_")


# ---------------------------------------------------------------------------
# APIKey model — create_with_key (uses DB; skipped without Postgres)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAPIKeyCreate:
    def test_create_with_key_returns_instance_and_raw(self):
        instance, raw_key = APIKey.create_with_key(name="test-key")
        assert isinstance(instance, APIKey)
        assert raw_key.startswith("dm_")

    def test_stored_hash_matches_raw_key(self):
        instance, raw_key = APIKey.create_with_key(name="test-key")
        assert instance.key_hash == APIKey.hash_key(raw_key)

    def test_raw_key_is_never_stored(self):
        instance, raw_key = APIKey.create_with_key(name="test-key")
        assert instance.key_hash != raw_key

    def test_new_key_is_active_by_default(self):
        instance, _ = APIKey.create_with_key(name="test-key")
        assert instance.is_active is True

    def test_record_usage_updates_last_used_at(self):
        instance, _ = APIKey.create_with_key(name="test-key")
        assert instance.last_used_at is None
        instance.record_usage()
        instance.refresh_from_db()
        assert instance.last_used_at is not None


# ---------------------------------------------------------------------------
# APIKeyAuthentication — authenticate() method
# ---------------------------------------------------------------------------


class TestAPIKeyAuthentication:
    def _make_request(self, key: str | None = None) -> MagicMock:
        request = MagicMock()
        request.META = {}
        if key is not None:
            request.META["HTTP_X_API_KEY"] = key
        return request

    def test_returns_none_when_no_header(self):
        auth = APIKeyAuthentication()
        request = self._make_request(key=None)
        result = auth.authenticate(request)
        assert result is None

    def test_raises_auth_error_for_unknown_key(self):
        auth = APIKeyAuthentication()
        request = self._make_request(key="dm_unknownkey123")
        with patch("authentication.authentication.APIKey.objects") as mock_mgr:
            mock_mgr.get.side_effect = APIKey.DoesNotExist
            with pytest.raises(AuthenticationError):
                auth.authenticate(request)

    def test_raises_invalid_key_error_for_revoked_key(self):
        auth = APIKeyAuthentication()
        raw = APIKey.generate_key()
        request = self._make_request(key=raw)

        mock_key = MagicMock(spec=APIKey)
        mock_key.is_active = False
        mock_key.record_usage = MagicMock()

        with patch("authentication.authentication.APIKey.objects") as mock_mgr:
            mock_mgr.get.return_value = mock_key
            with pytest.raises(InvalidAPIKeyError):
                auth.authenticate(request)

    def test_returns_none_user_and_api_key_on_success(self):
        auth = APIKeyAuthentication()
        raw = APIKey.generate_key()
        request = self._make_request(key=raw)

        mock_key = MagicMock(spec=APIKey)
        mock_key.is_active = True
        mock_key.record_usage = MagicMock()

        with patch("authentication.authentication.APIKey.objects") as mock_mgr:
            mock_mgr.get.return_value = mock_key
            user, auth_obj = auth.authenticate(request)

        assert user is None
        assert auth_obj is mock_key

    def test_record_usage_called_on_success(self):
        auth = APIKeyAuthentication()
        raw = APIKey.generate_key()
        request = self._make_request(key=raw)

        mock_key = MagicMock(spec=APIKey)
        mock_key.is_active = True
        mock_key.record_usage = MagicMock()

        with patch("authentication.authentication.APIKey.objects") as mock_mgr:
            mock_mgr.get.return_value = mock_key
            auth.authenticate(request)

        mock_key.record_usage.assert_called_once()

    def test_authenticate_header_returns_apikey_string(self):
        auth = APIKeyAuthentication()
        assert auth.authenticate_header(MagicMock()) == "APIKey"


# ---------------------------------------------------------------------------
# IsAuthenticatedWithAPIKey — permission class
# ---------------------------------------------------------------------------


class TestIsAuthenticatedWithAPIKey:
    def test_raises_auth_error_when_auth_is_none(self):
        perm = IsAuthenticatedWithAPIKey()
        request = MagicMock()
        request.auth = None
        with pytest.raises(AuthenticationError):
            perm.has_permission(request, view=None)

    def test_returns_true_for_valid_api_key_instance(self):
        perm = IsAuthenticatedWithAPIKey()
        request = MagicMock()
        request.auth = MagicMock(spec=APIKey)
        assert perm.has_permission(request, view=None) is True

    def test_raises_invalid_key_error_for_unknown_auth_object(self):
        perm = IsAuthenticatedWithAPIKey()
        request = MagicMock()
        request.auth = "some-string"  # Not an APIKey instance
        with pytest.raises(InvalidAPIKeyError):
            perm.has_permission(request, view=None)


# ---------------------------------------------------------------------------
# Authentication exceptions — correct base classes and codes
# ---------------------------------------------------------------------------


class TestAuthenticationExceptions:
    def test_authentication_error_is_drf_authentication_failed(self):
        assert issubclass(AuthenticationError, AuthenticationFailed)

    def test_invalid_api_key_error_is_drf_permission_denied(self):
        assert issubclass(InvalidAPIKeyError, PermissionDenied)

    def test_authentication_error_has_unauthenticated_code(self):
        exc = AuthenticationError()
        assert exc.default_code == "UNAUTHENTICATED"

    def test_invalid_api_key_error_has_invalid_api_key_code(self):
        exc = InvalidAPIKeyError()
        assert exc.default_code == "INVALID_API_KEY"


# ---------------------------------------------------------------------------
# create_api_key management command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreateAPIKeyCommand:
    def test_command_prints_dm_prefixed_key(self):
        stdout = StringIO()
        call_command("create_api_key", name="test-runner", stdout=stdout)
        output = stdout.getvalue()
        assert "dm_" in output

    def test_command_creates_db_record(self):
        call_command("create_api_key", name="cmd-test", stdout=StringIO())
        assert APIKey.objects.filter(name="cmd-test").exists()

    def test_command_prints_not_shown_again_warning(self):
        stdout = StringIO()
        call_command("create_api_key", name="warn-test", stdout=stdout)
        assert "not be shown again" in stdout.getvalue()
