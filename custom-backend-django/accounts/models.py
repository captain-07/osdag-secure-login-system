# Create your models here.
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    username = None  # we don't use username at all — email is the sole identifier

    objects = UserManager()

    # These two fields power account lockout (Step 4 of the next batch).
    # failed_login_attempts resets to 0 on any successful login.
    # locked_until is null unless the account is currently locked.
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"   # tells Django auth machinery to treat email as the login field
    REQUIRED_FIELDS = []       # createsuperuser only asks for email + password, nothing else

    def is_locked(self) -> bool:
        # Centralizing this check here (rather than repeating the comparison in every view)
        # means the lockout logic only lives in one place.
        return bool(self.locked_until and self.locked_until > timezone.now())

    # This will show email instead of object name
    def __str__(self):
        return self.email