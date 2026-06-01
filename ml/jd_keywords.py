"""
Extraction de mots-clés et critères structurés depuis l'offre v2 — version durcie.

Améliorations clés :
- Stop words proprement séparés (FR/EN) + anti-pollution (plus de fragments de JD spécifiques).
- Référentiel TECH_SKILLS (200+ compétences) qui contourne les filtres de longueur/casse.
- Détection des sigles 2-3 lettres (AWS, SQL, BI, CI, ETL, R, AI, ML, NLP, ERP, CRM, HR, JS, R&D).
- Détection des expressions techniques (.NET, C++, Node.js, ES6, CI/CD, REST API…).
- Pondération IDF heuristique (mots rares > mots fréquents).
- Patterns d'expérience et d'éducation robustes (fourchettes 5-10 ans, "5+ years", etc.).

API publique préservée :
- extract_keywords_from_job(job) -> list[str]
- extract_suggested_criteria(job) -> dict
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable

# ─────────────────────────────────────────────────────────────
# STOP WORDS — listes propres et auditées (FR + EN)
# ─────────────────────────────────────────────────────────────

# Mots vides anglais (courants, sans valeur informative pour le matching)
_STOP_WORDS_EN = frozenset({
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her", "was",
    "one", "our", "out", "has", "have", "its", "may", "who", "how", "why", "when",
    "what", "which", "that", "this", "with", "from", "their", "there", "they", "them",
    "then", "than", "been", "being", "into", "over", "such", "only", "just", "more",
    "some", "other", "about", "after", "before", "between", "under", "again", "during",
    "where", "through", "each", "very", "could", "should", "would", "will", "your",
    "any", "his", "yes", "yet", "off", "ago", "now", "few", "let", "any", "own",
    "able", "also", "with", "without", "while", "since", "until", "upon", "every",
    "many", "much", "well", "above", "below", "across", "around", "behind",
})

# Mots vides français
_STOP_WORDS_FR = frozenset({
    "les", "des", "une", "dans", "pour", "qui", "que", "est", "son", "sont", "aux",
    "pas", "sur", "tout", "toute", "tous", "toutes", "nous", "vous", "avec", "sans",
    "sous", "chez", "donc", "comme", "mais", "ou", "et", "si", "ce", "cette", "ces",
    "mon", "ton", "mes", "tes", "notre", "votre", "leur", "leurs", "plus", "fait",
    "faites", "se", "elle", "ils", "elles", "ainsi", "alors", "afin", "aussi",
    "celui", "celle", "ceux", "ici", "ainsi", "encore", "puis", "très", "tres",
    "bien", "haut", "bas", "doit", "doivent", "peut", "peuvent", "rendre", "selon",
    "lors", "déjà", "deja", "non", "oui", "voir", "vue", "etre", "être", "avoir",
    "cela", "celà", "soit", "vers", "via", "autre", "autres", "même", "meme",
    "entre", "depuis", "avant", "après", "apres", "pendant", "jusqu", "quand",
    "des", "du", "un", "le", "la", "de", "à", "au", "a", "en", "il", "ne",
    "j", "l", "d", "n", "m", "t", "s", "qu", "lui", "leur", "moi", "toi", "soi",
    "y", "où", "ou", "par",
})

# Mots métier neutres (présents dans toutes les offres, peu discriminants)
_STOP_WORDS_BUSINESS = frozenset({
    "poste", "offre", "emploi", "candidat", "candidate", "candidats", "candidates",
    "entreprise", "société", "societe", "company", "position", "job", "role",
    "rôle", "mission", "missions", "tâche", "taches", "tâches", "task", "tasks",
    "objectif", "objectifs", "objective", "objectives", "responsabilité",
    "responsabilités", "responsibility", "responsibilities", "profil", "profile",
    "compétence", "competence", "compétences", "competences", "skill", "skills",
    "expérience", "experience", "experiences", "expériences", "année", "années",
    "annee", "annees", "an", "year", "years", "mois", "month", "months",
    "jour", "jours", "day", "days", "semaine", "week", "type", "types",
    "niveau", "niveaux", "level", "levels", "lieu", "location", "ville", "city",
    "pays", "country", "salaire", "salary", "rémunération", "remuneration",
    "horaire", "hours", "temps", "time", "période", "period", "date", "dates",
    "début", "debut", "fin", "end", "start", "actuel", "actual", "current",
    "nouveau", "new", "ancien", "old", "membre", "member", "équipe", "team",
    "groupe", "group", "service", "department", "département", "departement",
    "diplôme", "diplome", "diploma", "degree", "formation", "training",
    "étude", "etude", "études", "etudes", "education", "study", "studies",
    "stage", "stages", "internship", "junior", "senior", "confirmé", "confirme",
    "fort", "forte", "bon", "bonne", "grand", "grande", "petit", "petite",
    "premier", "première", "deuxième", "troisième", "quatrième",
    "first", "second", "third", "fourth", "fifth", "last",
    "principal", "principale", "secondaire", "general", "générale", "general",
    "spécifique", "specifique", "specific", "spécialisé", "specialise",
})

# Mots vides combinés (utilisés par les fonctions internes)
STOP_WORDS = _STOP_WORDS_EN | _STOP_WORDS_FR | _STOP_WORDS_BUSINESS


# ─────────────────────────────────────────────────────────────
# RÉFÉRENTIEL DE COMPÉTENCES TECHNIQUES
# ─────────────────────────────────────────────────────────────
# Liste curated : whitelist qui contourne les filtres de longueur et de stop words.
# La détection est insensible à la casse. Les variantes orthographiques sont gérées
# par text_normalize (synonymes + fuzzy).

TECH_SKILLS: frozenset[str] = frozenset({
    # Langages
    "python", "java", "javascript", "typescript", "c", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "perl",
    "bash", "shell", "powershell", "sql", "plsql", "vba", "delphi", "objective-c",
    "dart", "elixir", "erlang", "haskell", "lua", "groovy", "fortran", "cobol",
    "abap", "assembly", "solidity",
    # Frameworks web
    "django", "flask", "fastapi", "tornado", "pyramid", "bottle",
    "react", "angular", "vue", "vue.js", "nuxt", "next.js", "svelte", "ember",
    "express", "nestjs", "koa", "node.js", "nodejs",
    "spring", "springboot", "spring-boot", "hibernate", "struts",
    "laravel", "symfony", "codeigniter", "yii", "zend",
    "rails", "ruby-on-rails", "sinatra",
    ".net", "asp.net", "blazor", "wpf", "winforms", "xamarin", "maui",
    # Data / ML
    "pandas", "numpy", "scipy", "scikit-learn", "sklearn", "tensorflow", "keras",
    "pytorch", "xgboost", "lightgbm", "catboost", "huggingface", "transformers",
    "spark", "pyspark", "hadoop", "hive", "pig", "kafka", "airflow", "dbt", "luigi",
    "jupyter", "anaconda", "rstudio", "tableau", "power-bi", "powerbi", "qlik",
    "looker", "metabase", "superset", "grafana", "kibana", "elasticsearch",
    "matplotlib", "seaborn", "plotly", "bokeh", "dash", "streamlit",
    "spacy", "nltk", "gensim", "opencv", "yolo", "detectron",
    # Bases de données
    "postgresql", "postgres", "mysql", "mariadb", "sqlite", "oracle", "mssql",
    "sql-server", "mongodb", "cassandra", "redis", "memcached", "dynamodb",
    "couchdb", "neo4j", "influxdb", "snowflake", "bigquery", "redshift", "athena",
    "clickhouse", "firebase", "firestore", "supabase",
    # Cloud / DevOps
    "aws", "azure", "gcp", "google-cloud", "ibm-cloud", "oracle-cloud", "alibaba-cloud",
    "ec2", "s3", "lambda", "rds", "iam", "cloudfront", "route53", "vpc", "ecs", "eks",
    "fargate", "sagemaker", "glue", "kinesis", "redshift",
    "docker", "kubernetes", "k8s", "helm", "openshift", "podman", "containerd",
    "terraform", "ansible", "puppet", "chef", "salt", "cloudformation", "pulumi",
    "jenkins", "gitlab-ci", "github-actions", "circleci", "travis", "bitbucket-pipelines",
    "argocd", "fluxcd", "spinnaker", "tekton",
    "prometheus", "datadog", "newrelic", "splunk", "sentry", "rollbar",
    "nginx", "apache", "haproxy", "traefik", "envoy", "istio", "linkerd",
    # Mobile
    "android", "ios", "flutter", "react-native", "ionic", "cordova",
    # Méthodologies
    "scrum", "kanban", "agile", "safe", "lean", "devops", "gitops", "tdd", "bdd",
    "ci/cd", "ci-cd", "cicd", "mvp", "poc",
    # Outils
    "git", "svn", "mercurial", "jira", "confluence", "trello", "asana", "notion",
    "slack", "teams", "linear", "miro", "figma", "sketch", "adobe-xd", "invision",
    "postman", "swagger", "openapi", "soapui", "insomnia",
    "vscode", "intellij", "pycharm", "eclipse", "vim", "emacs", "sublime",
    "linux", "ubuntu", "debian", "centos", "rhel", "fedora", "windows", "macos",
    # Protocoles & formats
    "rest", "graphql", "soap", "grpc", "websocket", "mqtt", "amqp", "json", "xml",
    "yaml", "csv", "parquet", "avro", "protobuf", "thrift",
    "oauth", "oauth2", "oidc", "saml", "jwt", "ldap", "kerberos", "sso",
    "tls", "ssl", "https", "tcp", "udp", "http", "http2", "http3",
    # Sigles 2-3 lettres (souvent jetés par les filtres classiques)
    "ai", "ml", "nlp", "cv", "dl", "iot", "ar", "vr", "xr", "ux", "ui", "hci",
    "bi", "ba", "da", "ds", "etl", "elt", "edw", "dwh", "dba", "qa", "qc",
    "rh", "hr", "erp", "crm", "cms", "scm", "plm", "wms", "tms", "pos",
    "api", "sdk", "ide", "vm", "vps", "cdn", "dns", "vpn", "lan", "wan",
    "ip", "tcp", "udp", "url", "uri", "uuid",
    "js", "ts", "fp", "oop", "mvc", "mvp", "mvvm", "soa",
    "ms", "msa", "ros", "rtos", "ftp", "sftp", "ssh", "rdp",
    "po", "pm", "tl", "cto", "ceo", "cfo", "cio", "ciso", "coo",
    "kpi", "okr", "roi", "tco", "sla", "slo", "rto", "rpo",
    # Domaines métier (utiles pour CV non-techniques)
    "marketing", "seo", "sem", "smo", "sea", "smm", "crm", "growth", "branding",
    "finance", "comptabilité", "comptabilite", "fiscalité", "fiscalite", "audit",
    "consolidation", "ifrs", "gaap", "sap", "oracle-financials", "sage",
    "logistique", "supply", "supply-chain", "achats", "procurement", "sourcing",
    "rh", "recrutement", "paie", "talent", "onboarding", "offboarding", "people",
    "vente", "ventes", "sales", "commercial", "b2b", "b2c", "saas", "paas", "iaas",
    "communication", "rp", "relations-presse", "événementiel", "evenementiel",
    "juridique", "droit", "contrat", "compliance", "rgpd", "gdpr", "ccpa",
    # Domaines humanitaire / ONG (présent dans le contexte AfricaHire+)
    "monitoring", "evaluation", "m&e", "cash", "cva", "cash-assistance",
    "humanitaire", "humanitarian", "wash", "nutrition", "food-security",
    "protection", "child-protection", "shelter", "ngo", "ong", "onu", "un",
    "unicef", "ocha", "undp", "unhcr", "who", "wfp", "ifrc", "icrc", "msf",
    "logframe", "logical-framework", "donor", "donor-reporting", "compliance",
})


# Modificateurs morphologiques pour générer les variantes des skills lors de la détection
def _skill_variants(skill: str) -> set[str]:
    """Génère les variantes orthographiques d'un skill (espace/tiret/sans séparateur)."""
    s = skill.lower().strip()
    variants = {s}
    if " " in s:
        variants.add(s.replace(" ", "-"))
        variants.add(s.replace(" ", ""))
    if "-" in s:
        variants.add(s.replace("-", " "))
        variants.add(s.replace("-", ""))
    if "." in s:
        variants.add(s.replace(".", ""))
    return variants


# Index inversé : variante orthographique → skill canonique
_SKILL_INDEX: dict[str, str] = {}
for _skill in TECH_SKILLS:
    for _v in _skill_variants(_skill):
        _SKILL_INDEX.setdefault(_v, _skill)


# ─────────────────────────────────────────────────────────────
# PATTERNS RÉGEX (expressions techniques + expérience + éducation)
# ─────────────────────────────────────────────────────────────

# Expressions techniques détectées via regex (sigles, CamelCase, .NET-style, C++…)
_TECH_EXPR_PATTERNS = [
    # Sigles 2-5 lettres en MAJUSCULES éventuellement séparés de & / -
    re.compile(r"\b[A-Z]{2,5}(?:[&/-][A-Z]{1,5})*\b"),
    # Mots avec point ou hashtag (.NET, Vue.js, C#, F#)
    re.compile(r"\b[A-Za-z][A-Za-z0-9]*[#.][A-Za-z0-9.+]+\b"),
    # Mots avec ++ (C++)
    re.compile(r"\b[A-Za-z][A-Za-z0-9]*\+\+"),
    # Versions / nombres collés (ES6, HTTP2, jQuery3, Vue3)
    re.compile(r"\b[A-Za-z]{2,}[0-9]{1,3}\b"),
    # CamelCase avec au moins 2 majuscules (JavaScript, PostgreSQL, MongoDB)
    re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]+\b"),
    # Expressions slash (CI/CD, B2B, B2C — gérées séparément, REST/SOAP)
    re.compile(r"\b[A-Za-z]{2,}/[A-Za-z0-9]{1,}\b"),
]

# Patterns pour le niveau d'études (FR/EN)
EDUCATION_PATTERNS = [
    (re.compile(r"\b(doctorat|phd|doctorate|doctoral)\b", re.IGNORECASE), "doctorat"),
    (re.compile(r"\b(master\s*2?|masters?|maîtrise|maitrise|msc|mba|m\.sc|m\.b\.a)\b", re.IGNORECASE), "master"),
    (re.compile(r"\b(ing[eé]nieur|engineer|m\.ing|école\s*d['\s]?ing[eé]nieur)\b", re.IGNORECASE), "ingénieur"),
    (re.compile(r"\b(licence|bachelor|bachelors?|bsc|b\.sc|bac\s*\+\s*3)\b", re.IGNORECASE), "licence"),
    (re.compile(r"\b(bts|but|dut|deust|bac\s*\+\s*2)\b", re.IGNORECASE), "bac+2"),
    (re.compile(r"\b(bac|baccalaur[eé]at|bacc|high\s*school)\b", re.IGNORECASE), "bac"),
    (re.compile(r"\b(diplôme|diplome|diploma|graduat)\b", re.IGNORECASE), "licence"),
]

# Patterns pour les années d'expérience (FR/EN)
_EXP_UNITS = r"(?:ans?|année[s]?|annee[s]?|years?|yrs?)"
_EXP_KW = r"(?:d['\s]?exp[eé]rience|d['\s]?exp[eé]r|of\s+experience|exp[eé]rience)"

EXPERIENCE_PATTERNS = [
    # "au moins 5 ans", "minimum 5 ans", "min. 5 ans", "at least 5 years"
    re.compile(
        r"(?:au\s+moins|minimum|min\.?|at\s+least)\s*[:\s]*(\d{1,2})\s*" + _EXP_UNITS,
        re.IGNORECASE,
    ),
    # "5+ ans", "5+ years"
    re.compile(r"(\d{1,2})\s*\+\s*" + _EXP_UNITS, re.IGNORECASE),
    # "5 ans d'expérience", "5 years of experience"
    re.compile(r"(\d{1,2})\s*" + _EXP_UNITS + r"\s*" + _EXP_KW, re.IGNORECASE),
    # "expérience confirmée de 5 ans", "experience of 5 years"
    re.compile(_EXP_KW + r"\s*(?:de|of)?\s*(\d{1,2})\s*" + _EXP_UNITS, re.IGNORECASE),
    # Fourchette "5-10 ans", "5 à 10 ans", "5 to 10 years" → on prend le min
    re.compile(r"(\d{1,2})\s*[-–à]\s*(\d{1,2})\s*" + _EXP_UNITS, re.IGNORECASE),
    re.compile(r"(\d{1,2})\s+to\s+(\d{1,2})\s*" + _EXP_UNITS, re.IGNORECASE),
    # "expérience : 5 ans"
    re.compile(r"(?:exp[eé]rience|experience)\s*[:\-]?\s*(\d{1,2})\s*" + _EXP_UNITS, re.IGNORECASE),
    # "5 ans et plus", "5 years and above", "5 ans minimum"
    re.compile(r"(\d{1,2})\s*" + _EXP_UNITS + r"\s*(?:et\s+plus|and\s+(?:more|above)|ou\s+plus|minimum|min)", re.IGNORECASE),
]


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _normalize(text: str, max_len: int = 100_000) -> str:
    """Compacte les espaces, met en minuscules, tronque."""
    if not text or not isinstance(text, str):
        return ""
    text = re.sub(r"\s+", " ", text.strip())
    return text[:max_len]


def _is_technical_token(token: str) -> bool:
    """
    Détermine si un token court (2-3 lettres) ou inhabituel mérite d'être conservé.
    Critères : présent dans TECH_SKILLS, ou contient chiffre/symbole, ou en MAJUSCULES significatives.
    """
    t = token.strip()
    if not t:
        return False
    t_lower = t.lower()
    if t_lower in _SKILL_INDEX:
        return True
    # Contient chiffre ou symbole spécial (ES6, C++, Vue.js)
    if re.search(r"[0-9+#./&]", t):
        return True
    # MAJUSCULES significatives (au moins 2 lettres consécutives en maj.)
    if re.match(r"^[A-Z]{2,5}$", t):
        return True
    return False


def _extract_tech_expressions(raw_text: str) -> list[str]:
    """Extrait les expressions techniques (sigles, CamelCase, .NET, C++, ES6…) du texte brut."""
    if not raw_text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for pattern in _TECH_EXPR_PATTERNS:
        for m in pattern.findall(raw_text):
            tok = m if isinstance(m, str) else (m[0] if m else "")
            if not tok:
                continue
            key = tok.lower()
            # Filtrer les faux positifs : mots vides en majuscules ("THE", "AND")
            if key in STOP_WORDS:
                continue
            if key not in seen:
                seen.add(key)
                found.append(tok)
    return found


def _detect_known_skills(text: str) -> list[str]:
    """Détecte les compétences du référentiel TECH_SKILLS dans le texte (lowercase)."""
    if not text:
        return []
    text_lower = text.lower()
    found: list[str] = []
    seen: set[str] = set()
    for variant, canonical in _SKILL_INDEX.items():
        if canonical in seen:
            continue
        # Recherche avec frontières de mot pour éviter les faux positifs
        # ex. "go" ne doit pas matcher "google", mais doit matcher "go," "Go programming"
        # On utilise une regex avec word boundaries
        # Pour les variantes contenant des caractères spéciaux (C++, .NET), regex simple
        escaped = re.escape(variant)
        # \b ne fonctionne pas avant/après caractères non-mots ; on adapte
        if re.search(r"[A-Za-z0-9]$", variant) and re.search(r"^[A-Za-z0-9]", variant):
            pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"
        else:
            pattern = escaped
        if re.search(pattern, text_lower):
            found.append(canonical)
            seen.add(canonical)
    return found


def _tokens_from_text(text: str, min_len: int = 3) -> list[str]:
    """
    Tokens normalisés depuis un texte. Conserve les tokens techniques courts.
    """
    # Regex large : lettres (Unicode) + chiffres + symboles techniques pour ne pas couper c++, .net
    tokens = re.findall(
        r"[a-z0-9éèêëàâäùûüîïôöçñ]+(?:[.+#/-][a-z0-9éèêëàâäùûüîïôöçñ]+)*",
        text.lower(),
    )
    out: list[str] = []
    for t in tokens:
        if t in STOP_WORDS:
            continue
        if len(t) >= min_len or _is_technical_token(t):
            out.append(t)
    return out


# IDF heuristique : poids inverse à la fréquence dans le texte global.
# Permet de privilégier les mots rares (plus discriminants).
def _idf_scores(tokens: list[str]) -> dict[str, float]:
    """Score IDF heuristique pour pondérer la rareté des tokens dans le texte."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {
        tok: 1.0 / (1.0 + (n / total))  # plus n est faible, plus le score est haut
        for tok, n in counts.items()
    }


# ─────────────────────────────────────────────────────────────
# API PUBLIQUE
# ─────────────────────────────────────────────────────────────

def extract_keywords_from_job(job: Any, max_words: int = 80, max_bigrams: int = 40) -> list[str]:
    """
    Extrait une liste de mots et expressions clés depuis l'offre.

    Ordre de priorité dans la liste retournée :
      1. Skills techniques détectés via le référentiel TECH_SKILLS (haute confiance).
      2. Expressions techniques (sigles, CamelCase, .NET-style) repérées par regex.
      3. Mots-clés rares (IDF) issus de requirements + title + description.
      4. Bigrams pertinents (les deux tokens ont une certaine longueur ou sont techniques).

    Le matching avec les CV sera ensuite renforcé par fuzzy + synonymes (text_normalize).
    """
    requirements_raw = str(getattr(job, "requirements", None) or "")
    title_raw = str(getattr(job, "title", None) or "")
    description_raw = str(getattr(job, "description", None) or "")
    benefits_raw = str(getattr(job, "benefits", None) or "")

    # Texte brut pour la détection des expressions techniques (casse préservée)
    raw_full = " ".join([title_raw, requirements_raw, description_raw, benefits_raw]).strip()
    if not raw_full:
        return []

    # 1) Skills connus (priorité absolue)
    known_skills = _detect_known_skills(raw_full)

    # 2) Expressions techniques (regex)
    tech_expressions = _extract_tech_expressions(raw_full)
    tech_expressions_lower = [
        e.lower() for e in tech_expressions if e.lower() not in known_skills
    ]

    # 3) Mots-clés IDF depuis le texte normalisé
    text_normalized = _normalize(raw_full)
    tokens = _tokens_from_text(text_normalized, min_len=3)
    idf = _idf_scores(tokens)
    # On exclut les mots déjà capturés en (1) et (2)
    already = set(known_skills) | set(tech_expressions_lower)
    candidates = [(t, idf[t]) for t in set(tokens) if t not in already]
    # Tri par score IDF décroissant
    candidates.sort(key=lambda x: -x[1])
    rare_words = [t for t, _ in candidates[:max_words]]

    # 4) Bigrams sur les tokens proches dans le texte (ordre conservé)
    bigrams: list[str] = []
    seen_bigrams: set[str] = set()
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if a in STOP_WORDS or b in STOP_WORDS:
            continue
        if not (len(a) >= 4 or _is_technical_token(a) or len(b) >= 4 or _is_technical_token(b)):
            continue
        bg = f"{a} {b}"
        if bg not in seen_bigrams:
            seen_bigrams.add(bg)
            bigrams.append(bg)
        if len(bigrams) >= max_bigrams:
            break

    result: list[str] = []
    result.extend(known_skills)
    result.extend(tech_expressions_lower)
    result.extend(rare_words)
    result.extend(bigrams)
    # Déduplication finale en préservant l'ordre
    seen: set[str] = set()
    return [x for x in result if not (x in seen or seen.add(x))]


def _extract_keywords_from_text(text: str, min_len: int = 4, max_keywords: int = 50) -> list[str]:
    """Compatibilité v1 — utilisé par extract_suggested_criteria."""
    text = _normalize(text)
    if not text:
        return []
    tokens = _tokens_from_text(text, min_len=min_len)
    idf = _idf_scores(tokens)
    candidates = sorted(set(tokens), key=lambda t: -idf.get(t, 0))
    bigrams: list[str] = []
    seen = set(candidates)
    for i in range(len(tokens) - 1):
        a, b = tokens[i], tokens[i + 1]
        if len(a) >= 4 or len(b) >= 4 or _is_technical_token(a) or _is_technical_token(b):
            bg = f"{a} {b}"
            if bg not in seen:
                seen.add(bg)
                bigrams.append(bg)
    result = candidates[: max(0, max_keywords - 15)] + bigrams[:15]
    return result[:max_keywords]


def _extract_keywords_from_requirements_and_title(job: Any, max_keywords: int = 50) -> list[str]:
    """Variante priorisant exigences + titre, fallback sur la description."""
    requirements = str(getattr(job, "requirements", None) or "").strip()
    title = str(getattr(job, "title", None) or "").strip()
    description = str(getattr(job, "description", None) or "").strip()

    text_primary = " ".join([requirements, title])
    if text_primary.strip():
        # Skills connus en priorité, puis mots rares
        known = _detect_known_skills(text_primary)
        tech = [e.lower() for e in _extract_tech_expressions(text_primary) if e.lower() not in known]
        rare = _extract_keywords_from_text(text_primary, min_len=4, max_keywords=max_keywords)
        merged = known + tech + rare
        seen: set[str] = set()
        deduped = [x for x in merged if not (x in seen or seen.add(x))]
        if deduped:
            return deduped[:max_keywords]

    if description:
        return _extract_keywords_from_text(description, min_len=4, max_keywords=max_keywords)
    return []


def _detect_min_experience(text: str) -> int | None:
    """
    Détecte un nombre d'années d'expérience minimum dans le texte.
    Priorité : "X+", "au moins X", "minimum X", "X ans d'expérience", fourchette → min.
    """
    if not text:
        return None
    candidates: list[int] = []
    for pattern in EXPERIENCE_PATTERNS:
        for m in pattern.finditer(text):
            g = m.groups()
            if not g:
                continue
            try:
                if len(g) >= 2 and g[1] is not None:
                    a, b = int(g[0]), int(g[1])
                    candidates.append(min(a, b))
                else:
                    candidates.append(int(g[0]))
            except (ValueError, TypeError):
                continue
    if not candidates:
        return None
    # Filtre des aberrations (ex. "expérience depuis 1995" → 1995 n'est pas une durée)
    plausible = [c for c in candidates if 0 < c <= 50]
    if not plausible:
        return None
    # On retourne la valeur médiane pour résister aux extrêmes
    plausible.sort()
    return plausible[len(plausible) // 2]


def _detect_education_level(text: str) -> str | None:
    """Détecte le niveau d'études le plus exigeant trouvé dans le texte."""
    if not text:
        return None
    # On parcourt les patterns du plus exigeant au moins exigeant
    for pattern, level in EDUCATION_PATTERNS:
        if pattern.search(text):
            return level
    return None


def extract_required_skills(job: Any, max_skills: int = 30) -> list[str]:
    """
    Extrait UNIQUEMENT les compétences techniques requises (référentiel TECH_SKILLS).
    Plus précis que extract_keywords_from_job lorsqu'on veut un filtrage strict.
    """
    raw_full = " ".join([
        str(getattr(job, "title", None) or ""),
        str(getattr(job, "requirements", None) or ""),
        str(getattr(job, "description", None) or ""),
    ])
    skills = _detect_known_skills(raw_full)
    return skills[:max_skills]


def extract_suggested_criteria(job: Any) -> dict[str, Any]:
    """
    Critères structurés pour l'UI Présélection/Sélection :
      - keywords      : mots-clés priorisés (skills + tech expressions + mots rares)
      - skills        : compétences strictes (référentiel uniquement) — pour skills_match
      - min_experience: années minimum détectées (None si absent)
      - education_level: niveau requis détecté (None si absent)
    """
    requirements_raw = str(getattr(job, "requirements", None) or "")
    description_raw = str(getattr(job, "description", None) or "")
    title_raw = str(getattr(job, "title", None) or "")
    full_text = " ".join([title_raw, requirements_raw, description_raw])

    keywords = _extract_keywords_from_requirements_and_title(job, max_keywords=50)
    skills = extract_required_skills(job, max_skills=30)
    min_experience = _detect_min_experience(full_text)
    education_level = _detect_education_level(full_text)

    return {
        "keywords": keywords,
        "skills": skills,
        "min_experience": min_experience,
        "education_level": education_level,
    }
