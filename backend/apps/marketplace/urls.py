from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path(
        "categories/",
        views.MarketplaceCategoryListView.as_view(),
        name="category-list",
    ),
    # Seller: own listings
    path("my/", views.MyListingListCreateView.as_view(), name="my-listing-list"),
    path(
        "my/<int:pk>/",
        views.MyListingDetailView.as_view(),
        name="my-listing-detail",
    ),
    path(
        "my/<int:pk>/publish/",
        views.PublishListingView.as_view(),
        name="my-listing-publish",
    ),
    path(
        "my/<int:pk>/unpublish/",
        views.UnpublishListingView.as_view(),
        name="my-listing-unpublish",
    ),
    # Seller: images on own listings
    path(
        "my/images/",
        views.MyListingImageListCreateView.as_view(),
        name="my-image-list",
    ),
    path(
        "my/images/<int:pk>/",
        views.MyListingImageDetailView.as_view(),
        name="my-image-detail",
    ),
    path(
        "my/images/<int:pk>/set-primary/",
        views.SetPrimaryImageView.as_view(),
        name="my-image-set-primary",
    ),
    # Admin moderation
    path(
        "admin/<int:pk>/approve/",
        views.ApproveListingView.as_view(),
        name="admin-approve",
    ),
    path(
        "admin/<int:pk>/reject/",
        views.RejectListingView.as_view(),
        name="admin-reject",
    ),
    path(
        "admin/<int:pk>/request-changes/",
        views.RequestListingChangesView.as_view(),
        name="admin-request-changes",
    ),
    path(
        "admin/<int:pk>/suspend/",
        views.SuspendListingView.as_view(),
        name="admin-suspend",
    ),
    path(
        "admin/<int:pk>/restore/",
        views.RestoreListingView.as_view(),
        name="admin-restore",
    ),
    # Public catalog
    path("", views.PublicListingListView.as_view(), name="public-list"),
    path("<int:pk>/", views.PublicListingDetailView.as_view(), name="public-detail"),
]
