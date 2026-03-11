from django.contrib import admin
from .models import Company, CompanyLicense


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'country', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'country')
    search_fields = ('name', 'email', 'city', 'country')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CompanyLicense)
class CompanyLicenseAdmin(admin.ModelAdmin):
    list_display = ('license_key', 'company', 'duration_months', 'start_date', 'end_date', 'is_valid_display', 'created_at')
    list_filter = ('duration_months',)
    search_fields = ('license_key', 'company__name')
    readonly_fields = ('license_key', 'created_at', 'updated_at')
    autocomplete_fields = ('company',)

    def is_valid_display(self, obj):
        return 'Oui' if obj.is_valid else 'Non'
    is_valid_display.short_description = 'Valide'

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return list(self.readonly_fields) + ['company']
        return self.readonly_fields
