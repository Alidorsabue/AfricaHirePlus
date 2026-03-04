# URLs API candidats : liste/création, détail, export Excel (scope tenant), mon profil (candidat)
from django.urls import path
from . import views

urlpatterns = [
    path('', views.CandidateListCreateView.as_view(), name='candidate-list-create'),
    path('me/', views.MyCandidateProfileView.as_view(), name='candidate-me'),
    path('<int:pk>/', views.CandidateDetailView.as_view(), name='candidate-detail'),
    path('export/xlsx/', views.ExportCandidatesExcelView.as_view(), name='candidate-export-excel'),
]
