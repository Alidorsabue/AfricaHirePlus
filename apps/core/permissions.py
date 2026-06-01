"""
Permissions multi-tenant : filtrer par company pour les Recruiters.
Rôles : Admin (SuperAdmin plateforme), Recruiter (par entreprise), Candidate.

NOTE SÉCURITÉ (P10) : `IsTenantOrSuperAdmin` et `IsRecruiterOrAdmin` ne se contentent
plus de vérifier l'authentification ; elles imposent désormais que le rôle soit
`recruiter` ou `super_admin`. Cela bloque tout candidat qui tenterait d'atteindre
les endpoints recruteur (création/édition de candidats, candidatures, etc.).
"""
from rest_framework import permissions


def _user_role(user) -> str | None:
    """Retourne le rôle du user de manière défensive (sans crasher)."""
    return getattr(user, 'role', None) if user is not None else None


def _is_recruiter_or_admin(user) -> bool:
    """True si le user est authentifié ET recruteur/super_admin."""
    if not user or not user.is_authenticated:
        return False
    return _user_role(user) in ('recruiter', 'super_admin')


class IsTenantOrSuperAdmin(permissions.BasePermission):
    """
    Accès recruteur ou super admin uniquement.
    Le filtrage par company (tenant) est fait dans `get_queryset` des vues.
    SuperAdmin voit tout ; Recruiter uniquement sa company.

    P10 : durci pour rejeter les candidats (avant : tout user authentifié passait).
    """

    message = "Cette ressource est réservée aux recruteurs."

    def has_permission(self, request, view):
        return _is_recruiter_or_admin(request.user)

    def has_object_permission(self, request, view, obj):
        if not _is_recruiter_or_admin(request.user):
            return False
        if request.user.is_super_admin:
            return True
        # Modèle Company : pas de champ company_id — comparer la PK à user.company_id
        from apps.companies.models import Company

        if isinstance(obj, Company):
            return obj.pk == request.user.company_id
        company_id = getattr(obj, 'company_id', None)
        if company_id is None:
            company_id = getattr(obj, 'company', None) and obj.company_id
        return company_id == request.user.company_id


class IsAdmin(permissions.BasePermission):
    """Accès réservé aux Super Admin (plateforme)."""

    message = "Réservé aux super administrateurs."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and _user_role(request.user) == 'super_admin'
        )


class IsRecruiterOrAdmin(permissions.BasePermission):
    """Recruiter ou Super Admin uniquement (durcie en P10)."""

    message = "Réservé aux recruteurs."

    def has_permission(self, request, view):
        return _is_recruiter_or_admin(request.user)


class IsCandidate(permissions.BasePermission):
    """Accès réservé aux utilisateurs avec le rôle candidat."""

    message = "Réservé aux candidats."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and _user_role(request.user) == 'candidate'
        )


class IsOwnerCandidate(permissions.BasePermission):
    """
    Permission au niveau objet pour un candidat : il ne peut accéder qu'à des
    objets liés à lui-même (`Candidate.user == request.user` ou
    `Application.candidate.user == request.user`).
    Combine bien avec `IsCandidate`.
    """

    message = "Vous ne pouvez accéder qu'à vos propres données."

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        # Application
        candidate = getattr(obj, 'candidate', None)
        if candidate is not None:
            return getattr(candidate, 'user_id', None) == request.user.id
        # Candidate
        return getattr(obj, 'user_id', None) == request.user.id
