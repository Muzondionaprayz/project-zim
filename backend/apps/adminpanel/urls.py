from django.urls import path

from . import views

app_name = "adminpanel"

urlpatterns = [
    # User administration
    path("users/", views.AdminUserListView.as_view(), name="user-list"),
    path("users/<int:pk>/", views.AdminUserDetailView.as_view(), name="user-detail"),
    path(
        "users/<int:pk>/role/",
        views.AdminChangeUserRoleView.as_view(),
        name="user-change-role",
    ),
    path(
        "users/<int:pk>/activate/",
        views.AdminActivateUserView.as_view(),
        name="user-activate",
    ),
    path(
        "users/<int:pk>/deactivate/",
        views.AdminDeactivateUserView.as_view(),
        name="user-deactivate",
    ),
    # Cross-domain visibility (read-only)
    path("businesses/", views.AdminBusinessListView.as_view(), name="business-list"),
    path(
        "marketplace-listings/",
        views.AdminMarketplaceListingListView.as_view(),
        name="marketplace-listing-list",
    ),
    path("reviews/", views.AdminReviewListView.as_view(), name="review-list"),
    # Audit log
    path("audit-logs/", views.AdminAuditLogListView.as_view(), name="audit-log-list"),
]
