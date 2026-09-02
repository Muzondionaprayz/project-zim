from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    path("my/", views.MyReviewListCreateView.as_view(), name="my-review-list"),
    path("my/<int:pk>/", views.MyReviewDetailView.as_view(), name="my-review-detail"),
    path(
        "admin/<int:pk>/hide/",
        views.HideReviewView.as_view(),
        name="admin-hide",
    ),
    path(
        "admin/<int:pk>/restore/",
        views.RestoreReviewView.as_view(),
        name="admin-restore",
    ),
    path("", views.PublicReviewListView.as_view(), name="public-list"),
    path("<int:pk>/", views.PublicReviewDetailView.as_view(), name="public-detail"),
]
