from django.urls import path

from query.views import SearchView

urlpatterns = [
    path("query/search/", SearchView.as_view(), name="query-search"),
]
