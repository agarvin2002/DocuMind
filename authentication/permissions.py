"""
IsAuthenticatedWithAPIKey — DRF permission class.

Checks that request.auth is a live APIKey instance. Raises:
  - AuthenticationError (401) when no key was provided at all
  - InvalidAPIKeyError (403) when auth is set but is not a valid APIKey
"""

from rest_framework.permissions import BasePermission

from authentication.exceptions import AuthenticationError, InvalidAPIKeyError
from authentication.models import APIKey


class IsAuthenticatedWithAPIKey(BasePermission):
    def has_permission(self, request, view) -> bool:
        if request.auth is None:
            # authenticate() returned None — no X-API-Key header was sent
            raise AuthenticationError()

        if isinstance(request.auth, APIKey):
            return True

        raise InvalidAPIKeyError()
