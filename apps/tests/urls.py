"""
URLs du module Tests.

Séparation stricte (P1) :
  - Endpoints recruteur/admin : /tests/, /tests/<pk>/, /tests/<pk>/questions/...
  - Endpoint CANDIDAT pour passer un test : /tests/<pk>/take/
    (utilise CandidateTestSerializer, sans correct_answer).
  - Sessions candidat : start-session/auto-save/tab-switch/upload/submit.
  - Review manuelle recruteur : /tests/answers/<pk>/review/ (P6).
"""
from django.urls import path

from . import views

urlpatterns = [
    # ---- Candidat : sessions et tests disponibles (avant <int:pk> pour ordre) ----
    path('my-sessions/', views.MyTestSessionsView.as_view(), name='test-my-sessions'),
    path('available-for-candidate/', views.MyAvailableTestsView.as_view(), name='test-available-for-candidate'),
    path('check-access/', views.CheckTestAccessView.as_view(), name='test-check-access'),

    # ---- Recruteur / Admin : gestion des tests ----
    path('', views.TestListCreateView.as_view(), name='test-list-create'),
    path('<int:pk>/', views.TestDetailView.as_view(), name='test-detail'),
    # P1 : endpoint candidat pour récupérer un test (sans correct_answer)
    path('<int:pk>/take/', views.CandidateTestTakeView.as_view(), name='test-candidate-take'),
    path('<int:test_id>/questions/<int:question_id>/attachment/', views.QuestionAttachmentUploadView.as_view(), name='test-question-attachment'),

    # ---- Session candidat ----
    path('start-session/', views.StartTestSessionView.as_view(), name='test-start-session'),
    path('auto-save/', views.AutoSaveTestAnswersView.as_view(), name='test-auto-save'),
    path('tab-switch/', views.TabSwitchView.as_view(), name='test-tab-switch'),
    path('upload-file/', views.UploadAnswerFileView.as_view(), name='test-upload-file'),
    path('submit-answers/', views.SubmitTestAnswersView.as_view(), name='test-submit-answers'),

    # ---- Exports & rapports recruteur ----
    path('export/results/xlsx/', views.ExportTestResultsExcelView.as_view(), name='test-export-results-excel'),
    path('results/', views.CandidateTestResultListCreateView.as_view(), name='testresult-list-create'),
    path('results/<int:pk>/', views.CandidateTestResultDetailView.as_view(), name='testresult-detail'),
    path('results/<int:pk>/report/', views.CandidateTestReportView.as_view(), name='testresult-report'),
    path('results/<int:pk>/report.pdf', views.CandidateTestReportPDFView.as_view(), name='testresult-report-pdf'),

    # ---- P6 : review manuelle recruteur (open_text / code / file) ----
    path('answers/<int:answer_id>/review/', views.ManualReviewAnswerView.as_view(), name='test-answer-review'),

    # ---- P8 : assignations correcteurs externes (côté recruteur) ----
    path(
        '<int:test_id>/correctors/',
        views.TestCorrectorAssignmentListCreateView.as_view(),
        name='test-corrector-list-create',
    ),
    path(
        'correctors/<int:pk>/',
        views.CorrectorAssignmentDetailView.as_view(),
        name='corrector-assignment-detail',
    ),
    path(
        'correctors/<int:pk>/resend/',
        views.CorrectorAssignmentResendView.as_view(),
        name='corrector-assignment-resend',
    ),

    # ---- P8 : interface correcteur (token magique, anonymisé) ----
    path(
        'correctors/auth/check/',
        views.CorrectorAuthCheckView.as_view(),
        name='corrector-auth-check',
    ),
    path(
        'correctors/sessions/',
        views.CorrectorSessionsListView.as_view(),
        name='corrector-sessions-list',
    ),
    path(
        'correctors/sessions/<int:pk>/',
        views.CorrectorSessionDetailView.as_view(),
        name='corrector-session-detail',
    ),
    path(
        'correctors/answers/<int:answer_id>/review/',
        views.CorrectorReviewAnswerView.as_view(),
        name='corrector-answer-review',
    ),
]
