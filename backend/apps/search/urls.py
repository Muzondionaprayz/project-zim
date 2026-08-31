from django.urls import path

from . import views

app_name = "search"

urlpatterns = [
    path("nearby/", views.NearbySearchView.as_view(), name="nearby"),
    path("", views.UnifiedSearchView.as_view(), name="unified"),
]
