from django.contrib import admin

from analysis.models import AnalysisJob


@admin.register(AnalysisJob)
class AnalysisJobAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "workflow_type",
        "status",
        "created_at",
        "started_at",
        "completed_at",
    ]
    list_filter = ["status", "workflow_type"]
    readonly_fields = [
        "id",
        "workflow_type",
        "input_data",
        "result_data",
        "error_message",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at"]
