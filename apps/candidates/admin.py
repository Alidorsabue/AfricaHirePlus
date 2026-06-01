from django.contrib import admin
from .models import Candidate


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'first_name', 'last_name', 'company', 'country',
        'experience_years', 'is_anonymized', 'created_at',
    )
    list_filter = ('company', 'country', 'is_anonymized')
    search_fields = ('email', 'first_name', 'last_name', 'raw_cv_text')
    readonly_fields = ('created_at', 'updated_at', 'is_anonymized', 'anonymized_at')
    actions = ['anonymize_selected']

    @admin.action(description='Anonymiser les candidats sélectionnés (RGPD)')
    def anonymize_selected(self, request, queryset):
        count = 0
        for c in queryset:
            try:
                c.anonymize()
                count += 1
            except Exception:
                continue
        self.message_user(request, f'{count} candidat(s) anonymisé(s).')
