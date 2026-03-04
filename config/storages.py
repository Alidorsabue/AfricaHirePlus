"""
Storage S3 (AWS compatible) pour médias et statiques.
"""
import os
from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class MediaS3Storage(S3Boto3Storage):
    """Stockage des fichiers uploadés (CV, pièces jointes) sur S3."""
    location = 'media'
    default_acl = getattr(settings, 'AWS_DEFAULT_ACL', 'private')
    file_overwrite = False
    custom_domain = getattr(settings, 'AWS_S3_CUSTOM_DOMAIN', None)
    endpoint_url = getattr(settings, 'AWS_S3_ENDPOINT_URL', None)


class StaticS3Storage(S3Boto3Storage):
    """Optionnel : statiques sur S3."""
    location = 'static'
    default_acl = 'public-read'
