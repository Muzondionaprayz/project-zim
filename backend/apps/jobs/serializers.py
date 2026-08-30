from rest_framework import serializers

from apps.accounts.models import User

from .models import Job, JobApplication, JobCategory


class JobCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobCategory
        fields = ["id", "name", "slug", "description"]


class JobPublicListSerializer(serializers.ModelSerializer):
    """
    Used for the public job catalog list. Excludes `employer` entirely
    (mirrors Business's exclusion of `owner`) — public job seekers
    don't need the poster's account details, just the job itself.
    """

    category = JobCategorySerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "slug",
            "category",
            "city",
            "province",
            "job_type",
            "budget",
            "budget_type",
            "deadline",
        ]


class JobPublicDetailSerializer(serializers.ModelSerializer):
    """
    Used for public job detail. Only ever served for jobs already
    filtered to status=OPEN and not expired by the view's queryset.

    Excludes `employer` — no account information about the poster is
    exposed publicly.
    """

    category = JobCategorySerializer(read_only=True)

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "city",
            "province",
            "job_type",
            "budget",
            "budget_type",
            "deadline",
            "created_at",
            "updated_at",
        ]


class JobOwnerSerializer(serializers.ModelSerializer):
    """
    Read/write serializer for an employer's own job posting.

    `employer` is deliberately not a field here at all — set only in
    the view's perform_create from request.user, the same protection
    Business gets against owner spoofing. `status` is read-only:
    transitions only happen through the dedicated publish/close/
    mark-filled endpoints (see services.py).
    """

    category = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=JobCategory.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Job
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "category",
            "city",
            "province",
            "job_type",
            "budget",
            "budget_type",
            "deadline",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "status", "created_at", "updated_at"]


class ApplicantSummarySerializer(serializers.ModelSerializer):
    """
    Minimal applicant contact info, shown only to the employer whose
    job was applied to (never publicly, never to other applicants).
    """

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name"]


class JobApplicationSerializer(serializers.ModelSerializer):
    """
    Used by an applicant to apply to a job and to view their own
    applications. `applicant` is never a field here — set only in
    the view's perform_create from request.user.

    `job`'s queryset is restricted to currently OPEN jobs as a first
    layer of defense; validate() adds the checks a queryset alone
    can't express (expiry, self-application, duplicates) so each
    produces a clear field-level error instead of a generic one.
    """

    class Meta:
        model = JobApplication
        fields = [
            "id",
            "job",
            "cover_note",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "created_at", "updated_at"]
        extra_kwargs = {
            "job": {"queryset": Job.objects.filter(status=Job.Status.OPEN)}
        }

    def validate(self, attrs):
        job = attrs.get("job")
        if job is None:
            return attrs

        request = self.context["request"]

        if job.is_expired:
            raise serializers.ValidationError(
                {"job": "This job's application deadline has passed."}
            )
        if job.employer_id == request.user.id:
            raise serializers.ValidationError(
                {"job": "You cannot apply to your own job."}
            )
        if JobApplication.objects.filter(job=job, applicant=request.user).exists():
            raise serializers.ValidationError(
                {"job": "You have already applied to this job."}
            )

        return attrs


class EmployerJobApplicationSerializer(serializers.ModelSerializer):
    """
    Read-only view of an application, as seen by the employer whose
    job it was submitted to. Includes minimal applicant contact info
    so the employer can follow up — never exposed on any public or
    other-applicant-facing endpoint.
    """

    applicant = ApplicantSummarySerializer(read_only=True)

    class Meta:
        model = JobApplication
        fields = ["id", "applicant", "cover_note", "status", "created_at", "updated_at"]
