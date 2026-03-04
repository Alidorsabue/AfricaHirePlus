"""
Vue racine : page d'accueil API.
"""
from django.http import JsonResponse


def api_root(request):
    """Réponse JSON à la racine pour éviter 404 et indiquer les endpoints."""
    return JsonResponse({
        'name': 'AfricaHirePlus ATS API',
        'version': '1.0',
        'docs': 'API REST - Utilisez les endpoints ci-dessous.',
        'endpoints': {
            'auth': '/api/v1/auth/',
            'companies': '/api/v1/companies/',
            'jobs': '/api/v1/jobs/',
            'jobs_public': '/api/v1/jobs/public/',
            'candidates': '/api/v1/candidates/',
            'applications': '/api/v1/applications/',
            'applications_apply': '/api/v1/applications/public/apply/',
            'tests': '/api/v1/tests/',
            'emails': '/api/v1/emails/',
        },
        'admin': '/admin/',
    })
