from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import User, UserProfile


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["phone_number", "bio", "location", "avatar_url", "updated_at"]
        read_only_fields = ["updated_at"]


class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles new-account creation.

    Password is write-only and validated with Django's configured
    password validators (min length, common-password check, etc.).
    `role` is restricted to CLIENT/PROVIDER — nobody can self-register
    as ADMIN through this endpoint.
    """

    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(
        write_only=True, style={"input_type": "password"}
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "password",
            "password_confirm",
        ]

    def validate_role(self, value):
        allowed = {User.Role.CLIENT, User.Role.PROVIDER}
        if value not in allowed:
            raise serializers.ValidationError(
                "role must be one of: %s" % ", ".join(sorted(allowed))
            )
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        # Run Django's password validators (uses the User instance's
        # fields, e.g. UserAttributeSimilarityValidator, for context).
        temp_user = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        password_validation.validate_password(attrs["password"], user=temp_user)
        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data.setdefault("role", User.Role.CLIENT)
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserSerializer(serializers.ModelSerializer):
    """Read/update serializer for the authenticated user's own account."""

    profile = UserProfileSerializer(required=False)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "date_joined",
            "profile",
        ]
        read_only_fields = ["id", "email", "role", "date_joined"]

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if profile_data is not None:
            profile = instance.profile
            for attr, value in profile_data.items():
                setattr(profile, attr, value)
            profile.save()

        return instance
