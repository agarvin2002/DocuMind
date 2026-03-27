import uuid

from django.db import models


class AnalysisJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    class WorkflowType(models.TextChoices):
        MULTI_HOP = "multi_hop", "Multi-Hop Query"
        COMPARISON = "comparison", "Document Comparison"
        CONTRADICTION = "contradiction", "Contradiction Detection"
        SIMPLE = "simple", "Simple Pass-Through"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="SHA-256 fingerprint of (question, sorted document_ids, workflow_type). "
        "Prevents duplicate jobs on client retries.",
    )
    workflow_type = models.CharField(
        max_length=20, choices=WorkflowType.choices, db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    input_data = models.JSONField()
    result_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "workflow_type"]),
            models.Index(fields=["created_at"], name="analysisjob_created_at_idx"),
            models.Index(
                fields=["status", "created_at"],
                name="analysisjob_status_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"AnalysisJob({self.id}, {self.workflow_type}, {self.status})"
