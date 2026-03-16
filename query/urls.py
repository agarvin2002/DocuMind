from django.urls import path

from query.views import AskView, SearchView

urlpatterns = [
    path("query/search/", SearchView.as_view(), name="query-search"),
    path("query/ask/", AskView.as_view(), name="query-ask"),
]
