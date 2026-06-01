from django.contrib import admin
from .models import Application, MLScore, ApplicationAuditLog, ApplicationNote


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'candidate', 'job_offer', 'status', 'screening_score', 'preselection_score', 'selection_score',
        'is_manually_adjusted', 'applied_at',
    )
    list_filter = ('status', 'job_offer__company')
    search_fields = ('candidate__email', 'candidate__first_name', 'job_offer__title')
    raw_id_fields = ('job_offer', 'candidate')
    readonly_fields = ('applied_at', 'created_at', 'updated_at')


@admin.register(MLScore)
class MLScoreAdmin(admin.ModelAdmin):
    list_display = ('application', 'model_version', 'predicted_score', 'confidence_score', 'created_at')
    list_filter = ('model_version', 'created_at')
    search_fields = ('application__id',)
    raw_id_fields = ('application',)
    readonly_fields = ('created_at',)


@admin.register(ApplicationAuditLog)
class ApplicationAuditLogAdmin(admin.ModelAdmin):
    """Audit en lecture seule (P10.3)."""
    list_display = ('id', 'application', 'action', 'actor', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('application__id', 'actor__email', 'reason')
    raw_id_fields = ('application', 'actor')
    readonly_fields = (
        'application', 'actor', 'action', 'payload_before', 'payload_after',
        'reason', 'ip_address', 'user_agent', 'created_at',
    )
    ordering = ('-created_at',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Conservation de l'historique
        return request.user.is_superuser


@admin.register(ApplicationNote)
class ApplicationNoteAdmin(admin.ModelAdmin):
    """Notes internes recruteur (P10.9)."""
    list_display = ('id', 'application', 'author', 'is_pinned', 'created_at')
    list_filter = ('is_pinned', 'created_at')
    search_fields = ('body', 'application__id', 'author__email')
    raw_id_fields = ('application', 'author')
    readonly_fields = ('created_at', 'updated_at')
