from django.contrib import admin

from .models import EmailLog, EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'template_type', 'subject', 'is_active', 'updated_at')
    list_filter = ('template_type', 'company', 'is_active')
    search_fields = ('name', 'subject', 'body_html')


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    """
    Audit log lecture-seule des envois d'email. Les recruteurs / admins
    peuvent rechercher par destinataire ou message-id Brevo, filtrer par
    statut, et consulter l'erreur exacte en cas d'échec.
    """
    list_display = (
        'created_at', 'recipient_email', 'template_type', 'status',
        'provider', 'company', 'attempts',
    )
    list_filter = ('status', 'template_type', 'provider', 'company')
    search_fields = (
        'recipient_email', 'subject', 'provider_message_id',
        'error_message', 'related_object_type',
    )
    readonly_fields = (
        'created_at', 'updated_at', 'sent_at',
        'company', 'template_type', 'recipient_email', 'subject', 'status',
        'attempts', 'provider', 'provider_message_id', 'error_message',
        'related_application_id', 'related_object_type', 'related_object_id',
    )
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Les admins peuvent purger via la commande dédiée
        return request.user.is_superuser
