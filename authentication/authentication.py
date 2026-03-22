"""
APIKeyAuthentication — DRF authentication class.

Reads the X-API-Key request header, hashes it, and looks up the matching
APIKey row. Returns (None, api_key) on success so request.auth holds the
APIKey instance (used by permission class and rate-limit throttles).

Returns None (not raises) when no header is present, allowing
IsAuthenticatedWithAPIKey to produce the correct 401.
"""

import logging

from rest_framework.authentication import BaseAuthentication

from authentication.exceptions import AuthenticationError, InvalidAPIKeyError
from authentication.models import APIKey

logger = logging.getLogger(__name__)

_HEADER = "HTTP_X_API_KEY"


class APIKeyAuthentication(BaseAuthentication):
    def authenticate(self, request) -> tuple[None, APIKey] | None:
        raw_key = request.META.get(_HEADER)
        if not raw_key:
            return None  # No credentials — let permission class handle the 401

        key_hash = APIKey.hash_key(raw_key)

        try:
            api_key = APIKey.objects.get(key_hash=key_hash)
        except APIKey.DoesNotExist:
            logger.warning(
                "API key not recognised",
                extra={"key_prefix": raw_key[:6]},
            )
            raise AuthenticationError()

        if not api_key.is_active:
            logger.warning(
                "Revoked API key used",
                extra={"key_name": api_key.name},
            )
            raise InvalidAPIKeyError()

        api_key.record_usage()
        logger.debug("API key authenticated", extra={"key_name": api_key.name})
        return (None, api_key)

    def authenticate_header(self, request) -> str:
        return "APIKey"
