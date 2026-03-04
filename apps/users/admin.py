from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'username', 'role', 'company', 'is_active', 'date_joined')
    list_filter = ('role', 'is_active', 'company')
    search_fields = ('email', 'username', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    filter_horizontal = ()

    fieldsets = BaseUserAdmin.fieldsets + (
        ('AfricaHirePlus', {'fields': ('role', 'company', 'phone', 'avatar')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('AfricaHirePlus', {'fields': ('role', 'company', 'phone')}),
    )
