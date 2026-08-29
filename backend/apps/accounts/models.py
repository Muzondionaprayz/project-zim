from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    """
    Manager for the custom, email-based User model.

    Email is the unique identifier used for authentication — there is
    no separate username field.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("role", User.Role.CLIENT)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for Project Zim.

    Authenticates by email (no separate username). Carries a coarse
    `role` used for role-based permissioning across the platform;
    finer-grained, domain-specific permissions (e.g. business
    ownership) are handled by later phases, not here.
    """

    class Role(models.TextChoices):
        CLIENT = "client", _("Client")
        PROVIDER = "provider", _("Service Provider")
        ADMIN = "admin", _("Administrator")

    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    role = models.CharField(
        _("role"), max_length=20, choices=Role.choices, default=Role.CLIENT
    )

    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)
    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.email

    def get_short_name(self):
        return self.first_name or self.email

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_provider(self):
        return self.role == self.Role.PROVIDER


class UserProfile(models.Model):
    """
    Extended, optional profile information for a User.

    Kept separate from User itself so the auth-critical model stays
    small and stable; profile fields can grow without touching auth
    machinery. Created automatically for every new User via a signal.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    phone_number = models.CharField(max_length=20, blank=True)
    bio = models.TextField(max_length=1000, blank=True)
    location = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("user profile")
        verbose_name_plural = _("user profiles")

    def __str__(self):
        return f"Profile<{self.user.email}>"
