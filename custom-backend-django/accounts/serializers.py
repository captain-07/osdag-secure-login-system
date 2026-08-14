from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    # write_only=True means this field is accepted on input but never included
    # in any response — the last thing you want is a hashed or plain password
    # echoed back in JSON.
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["email", "password"]

    def create(self, validated_data):
        # create_user (not create / objects.create) is essential here —
        # it's the method that actually calls set_password() to hash the
        # password. Using create() directly would store it in plaintext.
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )


class UserSerializer(serializers.ModelSerializer):
    # Used by /me and inside the login response. Deliberately excludes
    # password, failed_login_attempts, locked_until — a user's own profile
    # view shouldn't leak internal security bookkeeping fields.
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "date_joined"]