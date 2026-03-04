from django.contrib import admin
from .models import JobOffer, PreselectionSettings, ScreeningRule, SelectionSettings


class ScreeningRuleInline(admin.TabularInline):
    model = ScreeningRule
    extra = 0


class PreselectionSettingsInline(admin.StackedInline):
    model = PreselectionSettings
    extra = 0
    max_num = 1


class SelectionSettingsInline(admin.StackedInline):
    model = SelectionSettings
    extra = 0
    max_num = 1


@admin.register(JobOffer)
class JobOfferAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'status', 'contract_type', 'country', 'deadline', 'published_at', 'created_at')
    list_filter = ('status', 'contract_type', 'company', 'country')
    search_fields = ('title', 'description', 'location')
    inlines = [ScreeningRuleInline, PreselectionSettingsInline, SelectionSettingsInline]
    readonly_fields = ('published_at', 'closed_at', 'created_at', 'updated_at')


@admin.register(ScreeningRule)
class ScreeningRuleAdmin(admin.ModelAdmin):
    list_display = ('job_offer', 'rule_type', 'is_required', 'order')
    list_filter = ('rule_type',)


@admin.register(PreselectionSettings)
class PreselectionSettingsAdmin(admin.ModelAdmin):
    list_display = ('job_offer', 'score_threshold', 'max_candidates')


@admin.register(SelectionSettings)
class SelectionSettingsAdmin(admin.ModelAdmin):
    list_display = ('job_offer', 'score_threshold', 'max_candidates', 'selection_mode')
