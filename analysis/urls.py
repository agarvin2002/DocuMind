from django.urls import path

from analysis.views import AnalysisJobCreateView, AnalysisJobDetailView

urlpatterns = [
    path("analysis/", AnalysisJobCreateView.as_view()),
    path("analysis/<uuid:job_id>/", AnalysisJobDetailView.as_view()),
]
