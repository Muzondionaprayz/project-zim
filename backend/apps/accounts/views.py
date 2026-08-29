from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import User
from .serializers import RegisterSerializer, UserSerializer
from .tokens import EmailTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    """
    POST /api/v1/auth/register/

    Public endpoint. Creates a new account with role CLIENT or
    PROVIDER (ADMIN accounts cannot be self-registered). Does not
    return a JWT pair — clients log in separately after registering.
    """

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            UserSerializer(user).data, status=status.HTTP_201_CREATED
        )


class LoginView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/

    Exchanges email + password for a JWT access/refresh pair.
    """

    serializer_class = EmailTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


class RefreshView(TokenRefreshView):
    """POST /api/v1/auth/refresh/ — exchange a refresh token for a new access token."""

    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/v1/auth/me/

    Returns or updates the authenticated user's own account and
    profile. Requires a valid access token; nothing here is
    reachable by anyone other than the token's owner.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
