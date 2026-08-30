from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    path(
        "categories/",
        views.ServiceCategoryListView.as_view(),
        name="category-list",
    ),
    path(
        "my/",
        views.MyServiceListCreateView.as_view(),
        name="my-service-list",
    ),
    path(
        "my/<int:pk>/",
        views.MyServiceDetailView.as_view(),
        name="my-service-detail",
    ),
    path(
        "my/<int:pk>/activate/",
        views.ActivateServiceView.as_view(),
        name="my-service-activate",
    ),
    path(
        "my/<int:pk>/deactivate/",
        views.DeactivateServiceView.as_view(),
        name="my-service-deactivate",
    ),
    path("", views.PublicServiceListView.as_view(), name="public-list"),
    path("<int:pk>/", views.PublicServiceDetailView.as_view(), name="public-detail"),
]
