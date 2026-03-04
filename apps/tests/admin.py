from django.contrib import admin
from .models import Test, Question, CandidateTestResult


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'test_type', 'duration_minutes', 'passing_score', 'is_active')
    list_filter = ('test_type', 'company', 'is_active')
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('test', 'question_type', 'order', 'points')
    list_filter = ('question_type',)


@admin.register(CandidateTestResult)
class CandidateTestResultAdmin(admin.ModelAdmin):
    list_display = ('application', 'test', 'status', 'score', 'max_score', 'submitted_at')
    list_filter = ('status', 'test')
