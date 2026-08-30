from django.urls import path

from . import views

app_name = "businesses"

urlpatterns = [
    path(
        "categories/",
        views.BusinessCategoryListView.as_view(),
        name="category-list",
    ),
    path(
        "my/",
        views.MyBusinessListCreateView.as_view(),
        name="my-business-list",
    ),
    path(
        "my/<int:pk>/",
        views.MyBusinessDetailView.as_view(),
        name="my-business-detail",
    ),
    path(
        "my/<int:pk>/submit/",
        views.SubmitForVerificationView.as_view(),
        name="my-business-submit",
    ),
    path(
        "admin/<int:pk>/approve/",
        views.ApproveBusinessView.as_view(),
        name="admin-approve",
    ),
    path(
        "admin/<int:pk>/reject/",
        views.RejectBusinessView.as_view(),
        name="admin-reject",
    ),
    path(
        "admin/<int:pk>/request-changes/",
        views.RequestChangesView.as_view(),
        name="admin-request-changes",
    ),
    path(
        "admin/<int:pk>/suspend/",
        views.SuspendBusinessView.as_view(),
        name="admin-suspend",
    ),
    path(
        "admin/<int:pk>/restore/",
        views.RestoreBusinessView.as_view(),
        name="admin-restore",
    ),
    path("", views.PublicBusinessListView.as_view(), name="public-list"),
    path("<int:pk>/", views.PublicBusinessDetailView.as_view(), name="public-detail"),
]
