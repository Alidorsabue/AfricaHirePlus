"""
Wrapper HTML uniforme pour tous les emails transactionnels.

Objectifs :
  - Apparence professionnelle cohérente (header coloré, footer, bouton CTA).
  - Compatible Gmail / Outlook / Apple Mail (table-based, inline styles).
  - Conversion automatique HTML → texte brut pour les clients mail qui ne
    rendent pas le HTML (accessibility + spam filters).
  - Personnalisation par entreprise : nom + logo si disponible.

Aucune dépendance externe : pur Python / Django.
"""
from __future__ import annotations

import re
from html import escape, unescape
from typing import Optional

from django.conf import settings
from django.utils.safestring import mark_safe

# Couleurs et tailles. La palette colle au design système (teal-600).
PRIMARY_COLOR = '#0d9488'  # teal-600
PRIMARY_DARK = '#0f766e'   # teal-700
TEXT_COLOR = '#1f2937'     # slate-800
MUTED_COLOR = '#64748b'    # slate-500
BG_COLOR = '#f8fafc'       # slate-50
BORDER_COLOR = '#e2e8f0'   # slate-200


def render_branded_html(
    *,
    company_name: str,
    company_logo_url: Optional[str] = None,
    body_html: str,
    cta_label: Optional[str] = None,
    cta_url: Optional[str] = None,
    footer_note: Optional[str] = None,
    preheader: Optional[str] = None,
) -> str:
    """
    Compose un HTML email branded à partir d'un corps libre.

    Args:
      company_name: Nom affiché dans header + footer.
      company_logo_url: URL HTTPS du logo (≤ 200 px de large recommandé).
      body_html: HTML du corps (peut contenir <p>, <ul>, <strong>...).
      cta_label / cta_url: Bouton d'action principal (optionnel).
      footer_note: Mention complémentaire en pied (ex. "Vous recevez cet email…").
      preheader: Texte d'aperçu (≤ 100 chars, masqué visuellement).
    """
    preheader_html = ''
    if preheader:
        # Pré-header invisible : améliore l'affichage en boîte de réception
        preheader_html = (
            f'<div style="display:none;font-size:1px;color:{BG_COLOR};line-height:1px;'
            f'max-height:0;max-width:0;opacity:0;overflow:hidden;">'
            f'{escape(preheader)}</div>'
        )

    logo_block = ''
    if company_logo_url:
        logo_block = (
            f'<img src="{escape(company_logo_url)}" alt="{escape(company_name)}" '
            f'style="max-height:36px;display:block;margin:0 auto 8px auto;border:0;" />'
        )

    cta_block = ''
    if cta_label and cta_url:
        cta_block = f'''
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"
               style="margin:24px 0;">
          <tr>
            <td align="center" bgcolor="{PRIMARY_COLOR}"
                style="border-radius:6px;">
              <a href="{escape(cta_url)}"
                 style="display:inline-block;padding:12px 28px;
                        font-family:Arial,Helvetica,sans-serif;font-size:15px;
                        font-weight:600;color:#ffffff;text-decoration:none;
                        border-radius:6px;background-color:{PRIMARY_COLOR};">
                {escape(cta_label)}
              </a>
            </td>
          </tr>
        </table>
        <p style="font-size:12px;color:{MUTED_COLOR};margin:0 0 12px 0;">
          Si le bouton ne fonctionne pas, copiez-collez ce lien :
          <br><a href="{escape(cta_url)}" style="color:{PRIMARY_DARK};word-break:break-all;">
            {escape(cta_url)}
          </a>
        </p>
        '''

    footer_html = ''
    if footer_note:
        footer_html = (
            f'<p style="font-size:12px;color:{MUTED_COLOR};margin:16px 0 0 0;">'
            f'{escape(footer_note)}</p>'
        )

    powered_by_html = ''
    powered_by = getattr(settings, 'EMAIL_POWERED_BY_LABEL', 'AfricaHire+')
    if powered_by:
        powered_by_html = (
            f'<p style="font-size:11px;color:{MUTED_COLOR};margin:8px 0 0 0;">'
            f'Envoyé via <strong>{escape(powered_by)}</strong>.</p>'
        )

    html = f'''<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>{escape(company_name)}</title>
</head>
<body style="margin:0;padding:0;background-color:{BG_COLOR};
             font-family:Arial,Helvetica,sans-serif;color:{TEXT_COLOR};">
  {preheader_html}
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
         style="background-color:{BG_COLOR};padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0"
               width="100%" style="max-width:560px;background-color:#ffffff;
                                    border:1px solid {BORDER_COLOR};border-radius:8px;
                                    overflow:hidden;">
          <tr>
            <td style="background-color:{PRIMARY_COLOR};color:#ffffff;
                       padding:20px 24px;text-align:center;">
              {logo_block}
              <p style="margin:0;font-size:14px;font-weight:600;color:#ffffff;
                        letter-spacing:0.4px;text-transform:uppercase;">
                {escape(company_name)}
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 24px 28px;font-size:15px;line-height:1.55;
                       color:{TEXT_COLOR};">
              {body_html}
              {cta_block}
              {footer_html}
            </td>
          </tr>
          <tr>
            <td style="background-color:{BG_COLOR};padding:16px 24px;
                       text-align:center;border-top:1px solid {BORDER_COLOR};">
              <p style="font-size:12px;color:{MUTED_COLOR};margin:0;">
                Cet email vous a été envoyé par <strong>{escape(company_name)}</strong>.
              </p>
              {powered_by_html}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>'''
    return mark_safe(html)


_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'[ \t]+')
_NL_RE = re.compile(r'\n{3,}')


def html_to_text(html: str) -> str:
    """
    Conversion HTML → texte brut minimaliste (sans dépendance externe type
    `html2text`). Le résultat alimente la partie `text/plain` de l'email
    (clients sans HTML, anti-spam, accessibilité).
    """
    if not html:
        return ''
    s = html
    # Préserve les retours à la ligne sémantiques
    s = re.sub(r'<\s*br\s*/?\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</\s*p\s*>', '\n\n', s, flags=re.IGNORECASE)
    s = re.sub(r'</\s*li\s*>', '\n', s, flags=re.IGNORECASE)
    s = re.sub(r'<\s*li[^>]*>', ' - ', s, flags=re.IGNORECASE)
    s = re.sub(r'</?\s*(ul|ol)\s*>', '\n', s, flags=re.IGNORECASE)
    # Liens : "label (url)"
    s = re.sub(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r'\2 (\1)',
        s, flags=re.IGNORECASE | re.DOTALL,
    )
    # Nettoyage : tags restants + entités
    s = _TAG_RE.sub('', s)
    s = unescape(s)
    s = _WS_RE.sub(' ', s)
    s = _NL_RE.sub('\n\n', s)
    return s.strip()
