"""
APIKey model — stores hashed keys only, never raw values.

Key lifecycle:
  1. generate_key()       → raw key string (returned to caller, never stored)
  2. hash_key(raw)        → sha256 hex digest (stored in DB)
  3. create_with_key()    → returns (instance, raw_key) — raw_key shown once
  4. record_usage()       → updates last_used_at via UPDATE (not save())
"""

import hashlib
import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone


class APIKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        status = "active" if self.is_active else "revoked"
        return f"{self.name} ({status})"

    @classmethod
    def generate_key(cls) -> str:
        """Returns a new raw key. Never stored — caller is responsible for printing it once."""
        return f"dm_{secrets.token_urlsafe(32)}"

    @classmethod
    def hash_key(cls, raw_key: str) -> str:
        """Returns the SHA-256 hex digest of the raw key. This is what gets stored."""
        return hashlib.sha256(raw_key.encode()).hexdigest()

    @classmethod
    def create_with_key(cls, name: str) -> tuple["APIKey", str]:
        """
        Creates and saves a new APIKey. Returns (instance, raw_key).
        The raw_key is only available here — it must be shown to the user immediately.
        """
        raw_key = cls.generate_key()
        instance = cls.objects.create(
            name=name,
            key_hash=cls.hash_key(raw_key),
        )
        return instance, raw_key

    def record_usage(self) -> None:
        """
        Updates last_used_at without a full model save.
        Uses UPDATE on a single column to avoid signal overhead on every request.
        Skips the DB write if last_used_at was updated within the last 5 minutes
        — the in-memory value is already set from the auth lookup, so no extra
        DB query is needed to make this check.
        """
        if self.last_used_at and (timezone.now() - self.last_used_at) < timedelta(minutes=5):
            return
        APIKey.objects.filter(pk=self.pk).update(last_used_at=timezone.now())
