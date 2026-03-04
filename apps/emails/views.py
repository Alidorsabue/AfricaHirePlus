"""
Vues API templates d'emails : liste, création, détail, mise à jour, suppression (scope tenant).
Endpoint destinataires : GET ?job_offer_id=&template_type= pour récupérer les emails concernés.
"""
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import EmailTemplate
from .serializers import EmailTemplateSerializer
from .recipient_rules import get_recipient_statuses_for_type
from apps.core.permissions import IsTenantOrSuperAdmin
from apps.applications.models import Application
from apps.jobs.models import JobOffer


class EmailTemplateListCreateView(generics.ListCreateAPIView):
    """Liste et création de templates d'email (recruteur = sa company)."""
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsTenantOrSuperAdmin]
    pagination_class = None  # liste non paginée pour éviter 400 sur paramètres page

    def get_queryset(self):
        qs = EmailTemplate.objects.select_related('company')
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs

    def perform_create(self, serializer):
        # Si company non fourni (recruteur), utiliser l'entreprise de l'utilisateur.
        user = self.request.user
        company = serializer.validated_data.get('company')
        if not company and user.company_id:
            serializer.save(company_id=user.company_id)
        elif company:
            serializer.save(company=company)
        else:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'company': 'Ce champ est requis pour un administrateur plateforme.'})


class EmailTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Détail, modification et suppression d'un template d'email (scope tenant)."""
    serializer_class = EmailTemplateSerializer
    permission_classes = [IsTenantOrSuperAdmin]

    def get_queryset(self):
        qs = EmailTemplate.objects.all()
        company_id = self.request.user.get_company_id()
        if company_id is not None:
            qs = qs.filter(company_id=company_id)
        return qs


class EmailRecipientsView(APIView):
    """
    GET ?job_offer_id=&template_type=
    Retourne les adresses mail des candidats concernés pour l'offre et le type de template.
    """
    permission_classes = [IsTenantOrSuperAdmin]

    def get(self, request):
        job_offer_id = request.query_params.get('job_offer_id')
        template_type = request.query_params.get('template_type', '').strip()
        if not job_offer_id or not template_type:
            return Response(
                {'recipients': [], 'error': 'job_offer_id et template_type requis'},
                status=400,
            )
        try:
            job_offer_id = int(job_offer_id)
        except (TypeError, ValueError):
            return Response({'recipients': [], 'error': 'job_offer_id invalide'}, status=400)

        company_id = request.user.get_company_id()
        if company_id is None:
            return Response({'recipients': []})

        if not JobOffer.objects.filter(pk=job_offer_id, company_id=company_id).exists():
            return Response({'recipients': []})

        statuses = get_recipient_statuses_for_type(template_type)
        if not statuses:
            return Response({'recipients': []})

        applications = (
            Application.objects.filter(
                job_offer_id=job_offer_id,
                status__in=statuses,
                deleted_at__isnull=True,
            )
            .select_related('candidate')
            .order_by('candidate__email')
        )
        seen = set()
        recipients = []
        for app in applications:
            c = app.candidate
            if c.email in seen:
                continue
            seen.add(c.email)
            recipients.append({
                'email': c.email,
                'first_name': c.first_name or '',
                'last_name': c.last_name or '',
            })
        return Response({'recipients': recipients})
