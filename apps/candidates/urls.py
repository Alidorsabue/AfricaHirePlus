# URLs API candidats — P10 reinforced (tags, anonymize RGPD, export "mes données")
from django.urls import path
from . import views

urlpatterns = [
    path('', views.CandidateListCreateView.as_view(), name='candidate-list-create'),
    path('me/', views.MyCandidateProfileView.as_view(), name='candidate-me'),
    path('me/export/', views.MyCandidateDataExportView.as_view(), name='candidate-me-export'),
    path('<int:pk>/', views.CandidateDetailView.as_view(), name='candidate-detail'),
    path('<int:pk>/tags/', views.CandidateTagsView.as_view(), name='candidate-tags'),
    path('<int:pk>/anonymize/', views.CandidateAnonymizeView.as_view(), name='candidate-anonymize'),
    path('export/xlsx/', views.ExportCandidatesExcelView.as_view(), name='candidate-export-excel'),
]
