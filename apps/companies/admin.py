from django.contrib import admin
from .models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'country', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'country')
    search_fields = ('name', 'email', 'city', 'country')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
