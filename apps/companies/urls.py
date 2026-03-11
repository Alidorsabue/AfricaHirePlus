from django.urls import path
from . import views

urlpatterns = [
    path('', views.CompanyListCreateView.as_view(), name='company-list-create'),
    path('<int:pk>/', views.CompanyDetailView.as_view(), name='company-detail'),
    # Licences (superadmin)
    path('licenses/', views.CompanyLicenseListView.as_view(), name='companylicense-list'),
    path('licenses/<int:pk>/', views.CompanyLicenseDetailView.as_view(), name='companylicense-detail'),
    path('licenses/<int:pk>/renew/', views.CompanyLicenseRenewView.as_view(), name='companylicense-renew'),
]
