# URLs API offres : liste/création, détail, clôture, export Excel (tenant) ; public/liste et public/<slug> (sans auth)
from django.urls import path
from . import views

urlpatterns = [
    path('', views.JobOfferListCreateView.as_view(), name='joboffer-list-create'),
    path('<int:pk>/', views.JobOfferDetailView.as_view(), name='joboffer-detail'),
    path('<int:pk>/close/', views.JobOfferCloseView.as_view(), name='joboffer-close'),
    path('<int:pk>/refresh-scores/', views.JobOfferRefreshScoresView.as_view(), name='joboffer-refresh-scores'),
    path('<int:pk>/leaderboard/', views.JobOfferLeaderboardView.as_view(), name='joboffer-leaderboard'),
    path('<int:pk>/simulate-shortlist/', views.JobOfferSimulateShortlistView.as_view(), name='joboffer-simulate-shortlist'),
    path('<int:pk>/generate-shortlist/', views.JobOfferGenerateShortlistView.as_view(), name='joboffer-generate-shortlist'),
    path('<int:pk>/kpi/', views.JobOfferKpiView.as_view(), name='joboffer-kpi'),
    path('<int:pk>/export-shortlist/', views.JobOfferExportShortlistView.as_view(), name='joboffer-export-shortlist'),
    path('export/xlsx/', views.ExportJobOffersExcelView.as_view(), name='joboffer-export-excel'),
    path('public/', views.PublicJobOffersListView.as_view(), name='joboffer-public-list'),
    path('public/<slug:slug>/', views.PublicJobOfferDetailView.as_view(), name='joboffer-public-detail'),
]
