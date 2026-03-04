from django.contrib import admin
from .models import Application, MLScore


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
