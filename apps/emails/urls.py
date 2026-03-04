from django.urls import path
from . import views

urlpatterns = [
    path('templates/', views.EmailTemplateListCreateView.as_view(), name='emailtemplate-list-create'),
    path('templates/<int:pk>/', views.EmailTemplateDetailView.as_view(), name='emailtemplate-detail'),
    path('recipients/', views.EmailRecipientsView.as_view(), name='email-recipients'),
]
