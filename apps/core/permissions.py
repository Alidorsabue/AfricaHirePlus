"""
Permissions multi-tenant : filtrer par company pour les Recruiters.
Rôles : Admin (SuperAdmin plateforme), Recruiter (par entreprise).
"""
from rest_framework import permissions


class IsTenantOrSuperAdmin(permissions.BasePermission):
    """
    Accès autorisé pour tout utilisateur authentifié.
    Le filtrage par company (tenant) est fait dans get_queryset des vues.
    SuperAdmin voit tout ; Recruiter uniquement sa company.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Super admin : accès à tout ; recruteur : uniquement objets de sa company
        if request.user.is_super_admin:
            return True
        company_id = getattr(obj, 'company_id', None)
        if company_id is None:
            company_id = getattr(obj, 'company', None) and obj.company_id
        return company_id == request.user.company_id


class IsAdmin(permissions.BasePermission):
    """Accès réservé aux Super Admin (plateforme)."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'super_admin'
        )


class IsRecruiterOrAdmin(permissions.BasePermission):
    """Recruiter ou Admin (équivalent à IsTenantOrSuperAdmin)."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsCandidate(permissions.BasePermission):
    """Accès réservé aux utilisateurs avec le rôle candidat."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'candidate'
        )
