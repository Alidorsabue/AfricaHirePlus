from django.contrib import admin
from .models import EmailTemplate


@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'company', 'template_type', 'subject', 'is_active', 'updated_at')
    list_filter = ('template_type', 'company', 'is_active')
    search_fields = ('name', 'subject', 'body_html')
