"""
AfricaHirePlus - Configuration des URLs.
Racine = api_root ; admin Django ; API v1 : auth, companies, jobs, candidates, applications, tests, emails.
En DEBUG, sert les médias (fichiers uploadés) depuis MEDIA_ROOT.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from .views import api_root

urlpatterns = [
    path('', api_root),
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.users.urls')),
    path('api/v1/companies/', include('apps.companies.urls')),
    path('api/v1/jobs/', include('apps.jobs.urls')),
    path('api/v1/candidates/', include('apps.candidates.urls')),
    path('api/v1/applications/', include('apps.applications.urls')),
    path('api/v1/tests/', include('apps.tests.urls')),
    path('api/v1/emails/', include('apps.emails.urls')),
]

if settings.DEBUG and settings.MEDIA_ROOT:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
