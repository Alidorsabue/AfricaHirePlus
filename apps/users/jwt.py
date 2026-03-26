"""
JWT (SimpleJWT) personnalisé pour durcir la connexion.

Objectif : éviter tout "login" réussi si la réponse ne contient pas de tokens,
ou si l'utilisateur n'existe pas / est inactif.
"""

from __future__ import annotations

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView


class StrictTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    SimpleJWT valide déjà username/password via authenticate().
    On ajoute une couche de garde pour :
    - refuser explicitement l'utilisateur inactif
    - garantir la présence de access/refresh dans la réponse
    """

    default_error_messages = {
        "no_active_account": "Identifiants incorrects.",
        "inactive_account": "Compte désactivé.",
    }

    def validate(self, attrs):
        data = super().validate(attrs)

        # `self.user` est défini par le serializer parent après authenticate()
        user = getattr(self, "user", None)
        if not user:
            raise serializers.ValidationError({"detail": self.error_messages["no_active_account"]})
        if not getattr(user, "is_active", True):
            raise serializers.ValidationError({"detail": self.error_messages["inactive_account"]})

        # Garde-fou : si pour une raison quelconque les tokens ne sont pas présents, on échoue.
        if not data.get("access") or not data.get("refresh"):
            raise serializers.ValidationError({"detail": "Erreur d'authentification."})

        return data


class StrictTokenObtainPairView(TokenObtainPairView):
    serializer_class = StrictTokenObtainPairSerializer

