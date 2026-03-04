"""
Gestion centralisée des exceptions API.
"""
import logging

from rest_framework.views import exception_handler
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Format unifié des erreurs API."""
    response = exception_handler(exc, context)
    if response is not None:
        payload = {
            'success': False,
            'error': {
                'code': response.status_code,
                'message': str(exc),
                'details': response.data,
            },
        }
        response.data = payload
    else:
        logger.exception('Unhandled exception: %s', exc, extra={'context': context})
        response = Response(
            {
                'success': False,
                'error': {
                    'code': 500,
                    'message': 'Internal server error',
                    'details': None,
                },
            },
            status=500,
        )
    return response
