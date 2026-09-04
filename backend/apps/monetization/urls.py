from django.urls import path

from . import views

app_name = "monetization"

urlpatterns = [
    path("plans/", views.SubscriptionPlanListView.as_view(), name="plan-list"),
    # Owner self-service
    path(
        "my/subscriptions/",
        views.MySubscriptionListCreateView.as_view(),
        name="my-subscription-list",
    ),
    path(
        "my/subscriptions/<int:pk>/",
        views.MySubscriptionDetailView.as_view(),
        name="my-subscription-detail",
    ),
    path(
        "my/subscriptions/<int:pk>/cancel/",
        views.CancelMySubscriptionView.as_view(),
        name="my-subscription-cancel",
    ),
    path(
        "my/subscriptions/<int:pk>/transactions/",
        views.MyTransactionListCreateView.as_view(),
        name="my-transaction-list",
    ),
    # Admin
    path(
        "admin/subscriptions/",
        views.AdminSubscriptionListView.as_view(),
        name="admin-subscription-list",
    ),
    path(
        "admin/subscriptions/<int:pk>/activate/",
        views.AdminActivateSubscriptionView.as_view(),
        name="admin-subscription-activate",
    ),
    path(
        "admin/subscriptions/<int:pk>/cancel/",
        views.AdminCancelSubscriptionView.as_view(),
        name="admin-subscription-cancel",
    ),
    path(
        "admin/subscriptions/<int:pk>/expire/",
        views.AdminExpireSubscriptionView.as_view(),
        name="admin-subscription-expire",
    ),
    path(
        "admin/transactions/",
        views.AdminTransactionListView.as_view(),
        name="admin-transaction-list",
    ),
    path(
        "admin/transactions/<int:pk>/complete/",
        views.AdminCompleteTransactionView.as_view(),
        name="admin-transaction-complete",
    ),
    path(
        "admin/transactions/<int:pk>/fail/",
        views.AdminFailTransactionView.as_view(),
        name="admin-transaction-fail",
    ),
    path(
        "admin/transactions/<int:pk>/refund/",
        views.AdminRefundTransactionView.as_view(),
        name="admin-transaction-refund",
    ),
]
