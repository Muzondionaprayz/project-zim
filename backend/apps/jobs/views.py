from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import Job, JobApplication, JobCategory
from .permissions import IsApplicationOwner, IsJobOwner
from .serializers import (
    EmployerJobApplicationSerializer,
    JobApplicationSerializer,
    JobCategorySerializer,
    JobOwnerSerializer,
    JobPublicDetailSerializer,
    JobPublicListSerializer,
)


class JobCategoryListView(generics.ListAPIView):
    """GET /api/v1/jobs/categories/ — public list of active job categories."""

    queryset = JobCategory.objects.filter(is_active=True)
    serializer_class = JobCategorySerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


class PublicJobListView(generics.ListAPIView):
    """
    GET /api/v1/jobs/

    Public catalog of jobs. The queryset is hard-filtered to
    status=OPEN AND (deadline is null OR deadline in the future)
    regardless of any query parameter — draft, closed, filled, and
    expired jobs are never reachable here.

    Supports optional filtering via query params: category (slug),
    city, province, search (matches title/description).
    """

    serializer_class = JobPublicListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = (
            Job.objects.filter(status=Job.Status.OPEN)
            .filter(Q(deadline__isnull=True) | Q(deadline__gt=timezone.now()))
            .select_related("category")
        )

        params = self.request.query_params
        category = params.get("category")
        city = params.get("city")
        province = params.get("province")
        search = params.get("search")

        if category:
            queryset = queryset.filter(category__slug=category)
        if city:
            queryset = queryset.filter(city__iexact=city)
        if province:
            queryset = queryset.filter(province__iexact=province)
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | Q(description__icontains=search)
            )

        return queryset


class PublicJobDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/jobs/<pk>/

    Uses the same open + not-expired queryset as the list endpoint,
    so a draft/closed/filled/expired job 404s rather than leaking its
    existence or data.
    """

    serializer_class = JobPublicDetailSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return (
            Job.objects.filter(status=Job.Status.OPEN)
            .filter(Q(deadline__isnull=True) | Q(deadline__gt=timezone.now()))
            .select_related("category")
        )


class MyJobListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/jobs/my/ — list the authenticated user's own job postings
    POST /api/v1/jobs/my/ — create a new job posting

    Ownership always comes from request.user via perform_create.
    There is no writable `employer` field on the serializer, so any
    "employer" key in the request body is simply ignored by DRF.
    """

    serializer_class = JobOwnerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Job.objects.filter(employer=self.request.user).select_related(
            "category"
        )

    def perform_create(self, serializer):
        serializer.save(employer=self.request.user)


class MyJobDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/PUT/DELETE /api/v1/jobs/my/<pk>/

    Scoped to the authenticated user's own job postings. The queryset
    itself excludes other users' jobs, so requesting another user's
    job ID here 404s rather than 403s — consistent with not
    confirming the existence of data that isn't yours. IsJobOwner is
    kept as an explicit second layer of defense.
    """

    serializer_class = JobOwnerSerializer
    permission_classes = [permissions.IsAuthenticated, IsJobOwner]

    def get_queryset(self):
        return Job.objects.filter(employer=self.request.user).select_related(
            "category"
        )


class PublishJobView(APIView):
    """POST /api/v1/jobs/my/<pk>/publish/ — employer action: draft -> open."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, employer=request.user)
        try:
            services.publish_job(job)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(JobOwnerSerializer(job).data)


class CloseJobView(APIView):
    """POST /api/v1/jobs/my/<pk>/close/ — employer action: open -> closed."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, employer=request.user)
        try:
            services.close_job(job)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(JobOwnerSerializer(job).data)


class MarkJobFilledView(APIView):
    """POST /api/v1/jobs/my/<pk>/mark-filled/ — employer action: open/closed -> filled."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        job = get_object_or_404(Job, pk=pk, employer=request.user)
        try:
            services.mark_job_filled(job)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(JobOwnerSerializer(job).data)


class EmployerJobApplicationListView(generics.ListAPIView):
    """
    GET /api/v1/jobs/my/<pk>/applications/

    Employer-only: lists applications submitted to one of their own
    job postings. 404s (not 403s) if the job ID doesn't belong to the
    requesting user, same "don't confirm existence" reasoning as
    MyJobDetailView.
    """

    serializer_class = EmployerJobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        job = get_object_or_404(
            Job, pk=self.kwargs["pk"], employer=self.request.user
        )
        return JobApplication.objects.filter(job=job).select_related("applicant")


class ReviewApplicationView(APIView):
    """POST /api/v1/jobs/my/applications/<pk>/review/ — employer action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(
            JobApplication, pk=pk, job__employer=request.user
        )
        try:
            services.review_application(application)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(EmployerJobApplicationSerializer(application).data)


class AcceptApplicationView(APIView):
    """POST /api/v1/jobs/my/applications/<pk>/accept/ — employer action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(
            JobApplication, pk=pk, job__employer=request.user
        )
        try:
            services.accept_application(application)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(EmployerJobApplicationSerializer(application).data)


class RejectApplicationView(APIView):
    """POST /api/v1/jobs/my/applications/<pk>/reject/ — employer action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(
            JobApplication, pk=pk, job__employer=request.user
        )
        try:
            services.reject_application(application)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(EmployerJobApplicationSerializer(application).data)


class MyApplicationListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/jobs/applications/my/ — list the authenticated user's
    own job applications
    POST /api/v1/jobs/applications/my/ — apply to a job

    `applicant` always comes from request.user via perform_create.
    """

    serializer_class = JobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return JobApplication.objects.filter(
            applicant=self.request.user
        ).select_related("job")

    def perform_create(self, serializer):
        serializer.save(applicant=self.request.user)


class MyApplicationDetailView(generics.RetrieveAPIView):
    """
    GET /api/v1/jobs/applications/my/<pk>/

    Scoped to the authenticated user's own applications. No update or
    delete — an application is either withdrawn (via the dedicated
    action) or left as submitted for the employer to act on.
    """

    serializer_class = JobApplicationSerializer
    permission_classes = [permissions.IsAuthenticated, IsApplicationOwner]

    def get_queryset(self):
        return JobApplication.objects.filter(
            applicant=self.request.user
        ).select_related("job")


class WithdrawApplicationView(APIView):
    """POST /api/v1/jobs/applications/my/<pk>/withdraw/ — applicant action."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        application = get_object_or_404(
            JobApplication, pk=pk, applicant=request.user
        )
        try:
            services.withdraw_application(application)
        except DjangoValidationError as exc:
            raise DRFValidationError(exc.messages)
        return Response(JobApplicationSerializer(application).data)
