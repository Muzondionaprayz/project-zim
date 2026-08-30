from django.urls import path

from . import views

app_name = "jobs"

urlpatterns = [
    path(
        "categories/",
        views.JobCategoryListView.as_view(),
        name="category-list",
    ),
    # Employer: own jobs
    path("my/", views.MyJobListCreateView.as_view(), name="my-job-list"),
    path("my/<int:pk>/", views.MyJobDetailView.as_view(), name="my-job-detail"),
    path(
        "my/<int:pk>/publish/",
        views.PublishJobView.as_view(),
        name="my-job-publish",
    ),
    path(
        "my/<int:pk>/close/",
        views.CloseJobView.as_view(),
        name="my-job-close",
    ),
    path(
        "my/<int:pk>/mark-filled/",
        views.MarkJobFilledView.as_view(),
        name="my-job-mark-filled",
    ),
    path(
        "my/<int:pk>/applications/",
        views.EmployerJobApplicationListView.as_view(),
        name="my-job-applications",
    ),
    # Employer: acting on applications to their own jobs
    path(
        "my/applications/<int:pk>/review/",
        views.ReviewApplicationView.as_view(),
        name="my-application-review",
    ),
    path(
        "my/applications/<int:pk>/accept/",
        views.AcceptApplicationView.as_view(),
        name="my-application-accept",
    ),
    path(
        "my/applications/<int:pk>/reject/",
        views.RejectApplicationView.as_view(),
        name="my-application-reject",
    ),
    # Applicant: own applications
    path(
        "applications/my/",
        views.MyApplicationListCreateView.as_view(),
        name="my-applications-list",
    ),
    path(
        "applications/my/<int:pk>/",
        views.MyApplicationDetailView.as_view(),
        name="my-application-detail",
    ),
    path(
        "applications/my/<int:pk>/withdraw/",
        views.WithdrawApplicationView.as_view(),
        name="my-application-withdraw",
    ),
    # Public catalog
    path("", views.PublicJobListView.as_view(), name="public-list"),
    path("<int:pk>/", views.PublicJobDetailView.as_view(), name="public-detail"),
]
