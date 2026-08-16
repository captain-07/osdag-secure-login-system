from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from .views import RegisterView, LoginView, LogoutView, MeView

urlpatterns = [
    path("register", RegisterView.as_view(), name="register"),
    path("login", LoginView.as_view(), name="login"),
    path("logout", LogoutView.as_view(), name="logout"),
    path("me", MeView.as_view(), name="me"),
    # Used to exchange a refresh token for a fresh access token. With
    # ROTATE_REFRESH_TOKENS=True the old refresh token is also rotated
    # (and blacklisted), which is what makes the rotation config real.
    path("token/refresh", TokenRefreshView.as_view(), name="token_refresh"),
]