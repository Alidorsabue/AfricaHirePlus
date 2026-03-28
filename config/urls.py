"""
AfricaHirePlus - Configuration des URLs.
Racine = api_root ; admin Django ; API v1 : auth, companies, jobs, candidates, applications, tests, emails.
Médias : en DEBUG via static() ; en prod sans S3, /media/ sert MEDIA_ROOT (avatars, logos).
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

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

if settings.MEDIA_ROOT:
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    elif not getattr(settings, 'USE_S3', False):
        # Prod Railway / disque : sans cela les URLs /media/... renvoient 404 (avatars, logos).
        urlpatterns += [
            re_path(
                r'^media/(?P<path>.*)$',
                serve,
                {'document_root': settings.MEDIA_ROOT},
            ),
        ]
