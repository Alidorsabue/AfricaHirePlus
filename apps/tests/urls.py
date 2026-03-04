from django.urls import path
from . import views

urlpatterns = [
    # Candidat : mes sessions et tests disponibles (à placer avant <int:pk>)
    path('my-sessions/', views.MyTestSessionsView.as_view(), name='test-my-sessions'),
    path('available-for-candidate/', views.MyAvailableTestsView.as_view(), name='test-available-for-candidate'),
    path('check-access/', views.CheckTestAccessView.as_view(), name='test-check-access'),
    # Gestion des tests (recruteur / admin)
    path('', views.TestListCreateView.as_view(), name='test-list-create'),
    path('<int:pk>/', views.TestDetailView.as_view(), name='test-detail'),
    path('<int:test_id>/questions/<int:question_id>/attachment/', views.QuestionAttachmentUploadView.as_view(), name='test-question-attachment'),
    # Session de test côté candidat (timer + autosave + anti-triche)
    path('start-session/', views.StartTestSessionView.as_view(), name='test-start-session'),
    path('auto-save/', views.AutoSaveTestAnswersView.as_view(), name='test-auto-save'),
    path('tab-switch/', views.TabSwitchView.as_view(), name='test-tab-switch'),
    path('upload-file/', views.UploadAnswerFileView.as_view(), name='test-upload-file'),
    path('submit-answers/', views.SubmitTestAnswersView.as_view(), name='test-submit-answers'),
    # Export / rapports recruteur
    path('export/results/xlsx/', views.ExportTestResultsExcelView.as_view(), name='test-export-results-excel'),
    path('results/', views.CandidateTestResultListCreateView.as_view(), name='testresult-list-create'),
    path('results/<int:pk>/', views.CandidateTestResultDetailView.as_view(), name='testresult-detail'),
    path('results/<int:pk>/report/', views.CandidateTestReportView.as_view(), name='testresult-report'),
    path('results/<int:pk>/report.pdf', views.CandidateTestReportPDFView.as_view(), name='testresult-report-pdf'),
]

