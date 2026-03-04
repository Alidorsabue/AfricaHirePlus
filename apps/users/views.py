"""
Vues API utilisateurs : inscription (entreprise, recruteur, candidat), profil (Me).
"""
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .models import User
from .serializers import (
    UserSerializer,
    RegisterSerializer,
    RegisterCompanySerializer,
    RegisterRecruiterSerializer,
    RegisterCandidateSerializer,
)
from apps.core.permissions import IsAdmin


class RegisterView(generics.CreateAPIView):
    """Inscription générique (recruteur ou super admin selon contexte)."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class RegisterCompanyView(generics.GenericAPIView):
    """Inscription entreprise : crée l'entreprise + le premier compte recruteur."""
    serializer_class = RegisterCompanySerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {
                'message': 'Entreprise et compte recruteur créés.',
                'company_id': result['company'].id,
                'user': UserSerializer(result['user']).data,
            },
            status=status.HTTP_201_CREATED,
        )


class RegisterRecruiterView(generics.GenericAPIView):
    """Inscription recruteur : ajout d'un recruteur à une entreprise (réservé Admin)."""
    serializer_class = RegisterRecruiterSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'message': 'Recruteur créé.', 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class RegisterCandidateView(generics.GenericAPIView):
    """Inscription candidat : compte pour voir les offres et postuler."""
    serializer_class = RegisterCandidateSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {'message': 'Compte candidat créé.', 'user': UserSerializer(user).data},
            status=status.HTTP_201_CREATED,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """Profil de l'utilisateur connecté (GET/PATCH /api/users/me/)."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
