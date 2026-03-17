"""
analysis/serializers.py — Request validation and response shaping for analysis endpoints.

AnalysisRequestSerializer validates the POST /api/v1/analysis/ body.
AnalysisJobSerializer serializes an AnalysisJob ORM instance for GET responses.

Usage:
    serializer = AnalysisRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    data = serializer.validated_data
"""

from rest_framework import serializers

from analysis.models import AnalysisJob


class AnalysisRequestSerializer(serializers.Serializer):
    """Validates the POST body for POST /api/v1/analysis/."""

    question = serializers.CharField(
        min_length=1,
        max_length=2000,
        help_text="The question to investigate across the provided documents.",
    )
    document_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=10,
        help_text="UUIDs of the documents to analyse. Must have between 1 and 10 entries.",
    )
    workflow_type = serializers.ChoiceField(
        choices=AnalysisJob.WorkflowType.choices,
        required=False,
        default=None,
        allow_null=True,
        help_text=(
            "Agent workflow to run. One of: 'simple', 'multi_hop', 'comparison', "
            "'contradiction'. Defaults to 'multi_hop' when omitted."
        ),
    )


class AnalysisJobSerializer(serializers.ModelSerializer):
    """Serializes an AnalysisJob for GET and POST responses."""

    class Meta:
        model = AnalysisJob
        fields = [
            "id",
            "workflow_type",
            "status",
            "input_data",
            "result_data",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields
