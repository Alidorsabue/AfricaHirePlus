# URLs API candidatures : liste/création, mes candidatures (candidat), détail, statut, screening, postuler (public), export Excel
from django.urls import path
from . import views

urlpatterns = [
    path('', views.ApplicationListCreateView.as_view(), name='application-list-create'),
    path('mine/', views.MyApplicationsListView.as_view(), name='application-mine'),
    path('my-application/', views.MyApplicationByJobView.as_view(), name='application-my-by-job'),
    path('<int:pk>/', views.ApplicationDetailView.as_view(), name='application-detail'),
    path('<int:pk>/ats-breakdown/', views.ApplicationAtsBreakdownView.as_view(), name='application-ats-breakdown'),
    path('<int:pk>/status/', views.ApplicationStatusUpdateView.as_view(), name='application-status'),
    path('<int:pk>/manual-override/', views.ApplicationManualOverrideView.as_view(), name='application-manual-override'),
    path('<int:pk>/run-screening/', views.ApplicationRunScreeningView.as_view(), name='application-run-screening'),
    path('<int:pk>/predict-score/', views.ApplicationPredictScoreView.as_view(), name='application-predict-score'),
    path('public/apply/', views.PublicApplyView.as_view(), name='application-public-apply'),
    path('export/xlsx/', views.ExportApplicationsExcelView.as_view(), name='application-export-excel'),
    path('export/shortlisted/xlsx/', views.ExportShortlistedExcelView.as_view(), name='application-export-shortlisted-excel'),
]
