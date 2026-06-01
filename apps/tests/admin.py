from django.contrib import admin

from .models import (
    Answer,
    CandidateTestResult,
    CorrectorAssignment,
    Question,
    Section,
    Test,
    TestAccessGrant,
    TestAuditLog,
)


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    fields = ('order', 'question_type', 'text', 'points', 'numeric_tolerance')


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'company', 'test_type', 'duration_minutes',
        'total_score', 'passing_score', 'is_active',
        'shuffle_questions', 'questions_per_session',
    )
    list_filter = ('test_type', 'company', 'is_active', 'shuffle_questions')
    search_fields = ('title', 'description')
    inlines = [QuestionInline]


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('test', 'title', 'order')
    list_filter = ('test',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('test', 'question_type', 'order', 'points', 'numeric_tolerance')
    list_filter = ('question_type',)
    search_fields = ('text',)


class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 0
    readonly_fields = ('question', 'response', 'score_obtained', 'is_correct', 'pending_manual_review', 'file')
    can_delete = False


@admin.register(CandidateTestResult)
class CandidateTestResultAdmin(admin.ModelAdmin):
    list_display = (
        'application', 'test', 'status', 'score', 'max_score',
        'pending_review_points', 'is_passed', 'is_flagged', 'submitted_at',
    )
    list_filter = ('status', 'test', 'is_passed', 'is_flagged')
    search_fields = (
        'application__candidate__email',
        'application__candidate__first_name',
        'application__candidate__last_name',
    )
    readonly_fields = ('client_ip', 'last_seen_ip', 'question_order')
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = (
        'session', 'question', 'score_obtained', 'is_correct',
        'pending_manual_review',
    )
    list_filter = ('pending_manual_review', 'is_correct')


@admin.register(TestAccessGrant)
class TestAccessGrantAdmin(admin.ModelAdmin):
    list_display = ('test', 'application', 'is_revoked', 'used_at', 'expires_at', 'created_at')
    list_filter = ('is_revoked', 'test')
    search_fields = ('token', 'application__candidate__email')
    readonly_fields = ('token', 'used_at', 'created_at', 'updated_at')


@admin.register(TestAuditLog)
class TestAuditLogAdmin(admin.ModelAdmin):
    list_display = ('session', 'action', 'actor', 'corrector', 'created_at', 'client_ip')
    list_filter = ('action', 'created_at')
    search_fields = (
        'session__application__candidate__email', 'reason', 'corrector__email',
    )
    readonly_fields = (
        'session', 'answer', 'action', 'actor', 'corrector',
        'old_value', 'new_value', 'reason', 'client_ip', 'created_at',
    )


@admin.register(CorrectorAssignment)
class CorrectorAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'email', 'test', 'company', 'all_candidates',
        'is_revoked', 'expires_at', 'last_used_at', 'use_count', 'created_at',
    )
    list_filter = ('is_revoked', 'all_candidates', 'company', 'test')
    search_fields = ('email', 'full_name', 'token')
    readonly_fields = (
        'token', 'first_used_at', 'last_used_at', 'use_count',
        'revoked_at', 'revoked_by', 'created_at', 'updated_at',
    )
    filter_horizontal = ('assigned_applications',)
