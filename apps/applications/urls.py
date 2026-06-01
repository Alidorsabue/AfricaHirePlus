# URLs API candidatures (P10 reinforced)
from django.urls import path
from . import views

urlpatterns = [
    path('', views.ApplicationListCreateView.as_view(), name='application-list-create'),
    path('mine/', views.MyApplicationsListView.as_view(), name='application-mine'),
    path('my-application/', views.MyApplicationByJobView.as_view(), name='application-my-by-job'),
    path('bulk-status/', views.ApplicationBulkStatusView.as_view(), name='application-bulk-status'),
    path('<int:pk>/', views.ApplicationDetailView.as_view(), name='application-detail'),
    path('<int:pk>/ats-breakdown/', views.ApplicationAtsBreakdownView.as_view(), name='application-ats-breakdown'),
    path('<int:pk>/status/', views.ApplicationStatusUpdateView.as_view(), name='application-status'),
    path('<int:pk>/manual-override/', views.ApplicationManualOverrideView.as_view(), name='application-manual-override'),
    path('<int:pk>/run-screening/', views.ApplicationRunScreeningView.as_view(), name='application-run-screening'),
    path('<int:pk>/predict-score/', views.ApplicationPredictScoreView.as_view(), name='application-predict-score'),
    path('<int:pk>/withdraw/', views.MyApplicationWithdrawView.as_view(), name='application-withdraw'),
    # Notes internes (recruteur)
    path('<int:application_id>/notes/', views.ApplicationNoteListCreateView.as_view(), name='application-notes'),
    path('notes/<int:pk>/', views.ApplicationNoteDetailView.as_view(), name='application-note-detail'),
    # Audit log (recruteur)
    path('<int:application_id>/audit/', views.ApplicationAuditLogListView.as_view(), name='application-audit-log'),
    # Soumission publique
    path('public/apply/', views.PublicApplyView.as_view(), name='application-public-apply'),
    # Exports
    path('export/xlsx/', views.ExportApplicationsExcelView.as_view(), name='application-export-excel'),
    path('export/shortlisted/xlsx/', views.ExportShortlistedExcelView.as_view(), name='application-export-shortlisted-excel'),
]
