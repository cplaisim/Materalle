from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from .auth_serializers import RegisterSerializer, LoginSerializer, UserProfileSerializer
from .response import api_response


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                message="Validation failed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return api_response(
            data={"token": token.key, "user_id": user.pk, "username": user.username},
            message="Account created.",
            status_code=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return api_response(
                errors=serializer.errors,
                message="Validation failed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        user = authenticate(
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return api_response(
                message="Invalid credentials.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        token, _ = Token.objects.get_or_create(user=user)
        return api_response(
            data={"token": token.key, "user_id": user.pk, "username": user.username},
            message="Login successful.",
        )


class RefreshTokenView(APIView):
    """Rotate the user's token (simple token refresh)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Delete old token and create new one
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return api_response(
            data={"token": token.key},
            message="Token refreshed.",
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # BridgeUser (V2) carries claims directly — no ORM UserProfile exists.
        if getattr(user, "role", None) and not hasattr(user, "userprofile"):
            return api_response(data={
                "username": user.username,
                "email": getattr(user, "email", ""),
                "role": user.role,
                "phone_number": None,
                "address": None,
            })
        serializer = UserProfileSerializer(user.userprofile)
        return api_response(data=serializer.data)