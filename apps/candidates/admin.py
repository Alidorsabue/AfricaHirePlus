from django.contrib import admin
from .models import Candidate


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'company', 'country', 'experience_years', 'created_at')
    list_filter = ('company', 'country')
    search_fields = ('email', 'first_name', 'last_name', 'raw_cv_text')
    readonly_fields = ('created_at', 'updated_at')
