"""
Tests de durcissement ML — vérifient que les renforcements v2 ne laissent PAS éliminer
de bons CV à cause de failles techniques (mauvaise extraction, vocabulaire différent,
mots-clés pollués, sigles trop courts, etc.).
"""
from django.test import SimpleTestCase

from ml.jd_keywords import (
    STOP_WORDS,
    TECH_SKILLS,
    _detect_education_level,
    _detect_known_skills,
    _detect_min_experience,
    _extract_tech_expressions,
    _is_technical_token,
    extract_keywords_from_job,
    extract_required_skills,
    extract_suggested_criteria,
)
from ml.text_normalize import (
    fuzzy_match,
    keyword_matches_text,
    keyword_similarity,
    normalize_for_match,
    _canonical_synonym,
    _stem_token,
)


# ─────────────────────────────────────────────────────────────
# Fake job pour les tests (pas besoin de Django ORM)
# ─────────────────────────────────────────────────────────────

class _FakeJob:
    def __init__(self, title="", description="", requirements="", benefits=""):
        self.title = title
        self.description = description
        self.requirements = requirements
        self.benefits = benefits


# ─────────────────────────────────────────────────────────────
# Tests : extraction JD renforcée
# ─────────────────────────────────────────────────────────────

class JDKeywordsHardenedTestCase(SimpleTestCase):
    """Le moteur d'extraction JD ne doit plus rater les sigles techniques courts ni les expressions."""

    def test_stop_words_no_longer_polluted(self):
        """Les fragments d'une offre spécifique (concentrera, imo, structura...) ne sont plus dans STOP_WORDS."""
        leaks = {"concentrera", "assurera", "developpera", "transformera", "imo", "op", "nutri", "structura", "analy"}
        for w in leaks:
            self.assertNotIn(w, STOP_WORDS, f"'{w}' ne doit plus polluer STOP_WORDS")

    def test_tech_skills_contains_short_acronyms(self):
        """Les sigles techniques 2-3 lettres essentiels sont dans le référentiel."""
        for s in ["sql", "aws", "bi", "etl", "ml", "ai", "nlp", "rh", "hr", "ci/cd", "cv", "ux", "ui"]:
            self.assertIn(s, TECH_SKILLS, f"'{s}' doit être dans TECH_SKILLS")

    def test_detect_known_skills_finds_python(self):
        text = "Nous cherchons un développeur Python avec PostgreSQL et Docker."
        skills = _detect_known_skills(text)
        self.assertIn("python", skills)
        self.assertIn("postgresql", skills)
        self.assertIn("docker", skills)

    def test_detect_known_skills_handles_variants(self):
        """node.js / nodejs / node js doivent matcher la même compétence."""
        # 'node js' avec espace
        skills = _detect_known_skills("Stack JavaScript node js et postgres")
        self.assertIn("nodejs", skills)

    def test_tech_expressions_detect_dotnet_and_cpp(self):
        text = "Stack .NET, Vue.js, C++, REST API, CI/CD"
        expressions = _extract_tech_expressions(text)
        # On vérifie que les expressions techniques sont bien identifiées
        joined = " ".join(expressions).lower()
        self.assertIn(".net", joined)

    def test_is_technical_token_accepts_short_tech(self):
        self.assertTrue(_is_technical_token("aws"))
        self.assertTrue(_is_technical_token("c++"))
        self.assertTrue(_is_technical_token("ES6"))
        self.assertFalse(_is_technical_token("le"))

    def test_extract_keywords_prioritizes_known_skills(self):
        job = _FakeJob(
            title="Développeur Python Senior",
            requirements="5 ans d'expérience Python, Django, PostgreSQL, Docker, AWS, CI/CD requis.",
            description="Rejoignez notre équipe de développement backend cloud.",
        )
        keywords = extract_keywords_from_job(job)
        # Les skills connus doivent apparaître en tête
        self.assertIn("python", keywords)
        self.assertIn("django", keywords)
        self.assertIn("postgresql", keywords)
        self.assertIn("aws", keywords)

    def test_extract_required_skills_strict_filter(self):
        """extract_required_skills ne retourne QUE des compétences du référentiel."""
        job = _FakeJob(
            requirements="Maîtrise de Python, Django et AWS. Expérience humanitaire un plus.",
        )
        skills = extract_required_skills(job)
        for s in skills:
            self.assertIn(s, TECH_SKILLS, f"'{s}' doit être un skill du référentiel")


class ExperienceDetectionRobustTestCase(SimpleTestCase):
    """Les patterns d'expérience tolèrent les formulations courantes."""

    def test_au_moins_x_ans(self):
        self.assertEqual(_detect_min_experience("Au moins 5 ans d'expérience requis"), 5)

    def test_minimum_x_years(self):
        self.assertEqual(_detect_min_experience("Minimum 7 years of experience"), 7)

    def test_plus_notation(self):
        self.assertEqual(_detect_min_experience("10+ ans d'expérience"), 10)

    def test_range(self):
        """Une fourchette 5-10 retourne le min (5)."""
        self.assertEqual(_detect_min_experience("5-10 ans d'expérience"), 5)

    def test_filters_implausible_values(self):
        """Une date comme 1995 ne doit pas être retournée comme durée."""
        result = _detect_min_experience("Diplômé en 1995 dans le domaine.")
        # Soit None, soit une valeur plausible mais pas 1995
        if result is not None:
            self.assertLessEqual(result, 50)


class EducationDetectionTestCase(SimpleTestCase):
    """Détection de niveau hiérarchique correctement."""

    def test_phd(self):
        self.assertEqual(_detect_education_level("PhD in Computer Science required"), "doctorat")

    def test_master_variants(self):
        for txt in ["Master 2 en informatique", "MSc required", "MBA preferred", "Maîtrise"]:
            self.assertEqual(_detect_education_level(txt), "master", txt)

    def test_ingenieur(self):
        self.assertEqual(_detect_education_level("Ingénieur en informatique"), "ingénieur")

    def test_licence(self):
        for txt in ["Bachelor degree", "Licence informatique", "BSc required"]:
            self.assertEqual(_detect_education_level(txt), "licence", txt)


# ─────────────────────────────────────────────────────────────
# Tests : matching tolérant (P3)
# ─────────────────────────────────────────────────────────────

class TextNormalizationTestCase(SimpleTestCase):
    """Normalisation : accents, casse, apostrophes."""

    def test_accents_removed(self):
        self.assertEqual(normalize_for_match("Développeur"), "developpeur")

    def test_apostrophes_replaced(self):
        result = normalize_for_match("Gestion d'informations")
        self.assertEqual(result, "gestion d informations")


class StemmingTestCase(SimpleTestCase):
    """Stemming léger FR/EN."""

    def test_french_suffixes(self):
        self.assertNotEqual(_stem_token("developpement"), "developpement")
        # La racine doit être courte
        self.assertLess(len(_stem_token("developpement")), len("developpement"))

    def test_english_suffixes(self):
        self.assertEqual(_stem_token("managing")[:4], "mana")
        self.assertEqual(_stem_token("development")[:4], "deve")

    def test_short_words_unchanged(self):
        self.assertEqual(_stem_token("aws"), "aws")
        self.assertEqual(_stem_token("ml"), "ml")


class SynonymTestCase(SimpleTestCase):
    """Dictionnaire de synonymes tech."""

    def test_rh_to_canonical(self):
        self.assertEqual(_canonical_synonym("rh"), "ressources humaines")
        self.assertEqual(_canonical_synonym("HR"), "ressources humaines")

    def test_js_to_javascript(self):
        self.assertEqual(_canonical_synonym("js"), "javascript")

    def test_ml_to_canonical(self):
        self.assertEqual(_canonical_synonym("ml"), "apprentissage automatique")


class FuzzyMatchingTestCase(SimpleTestCase):
    """Fuzzy matching résistant aux fautes de frappe."""

    def test_exact_match(self):
        self.assertTrue(fuzzy_match("python", "j'utilise python au quotidien", threshold=0.85))

    def test_typo_tolerant(self):
        # "developper" vs "developpeur" (faute commune)
        self.assertTrue(fuzzy_match("developpeur", "je suis developper", threshold=0.85))

    def test_too_different(self):
        self.assertFalse(fuzzy_match("python", "javascript html css"))

    def test_short_token_not_fuzzy(self):
        """Tokens trop courts n'utilisent pas fuzzy (risque de faux positifs)."""
        self.assertFalse(fuzzy_match("ai", "j'aime"))


class KeywordMatchesTolerantTestCase(SimpleTestCase):
    """Le matching tolérant ne doit jamais rater un CV à cause d'un vocabulaire différent."""

    def test_match_with_accents(self):
        cv_normalized = normalize_for_match("Expert en développement Python")
        self.assertTrue(keyword_matches_text("Développement", cv_normalized))

    def test_match_singular_plural(self):
        cv_normalized = normalize_for_match("J'ai des compétences en bases de données")
        self.assertTrue(keyword_matches_text("compétence", cv_normalized))
        self.assertTrue(keyword_matches_text("base de donnée", cv_normalized))

    def test_match_with_synonym(self):
        """Le candidat dit 'developer', le critère exige 'développeur' → doit matcher."""
        cv_normalized = normalize_for_match("Senior backend developer")
        self.assertTrue(keyword_matches_text("développeur", cv_normalized))

    def test_match_with_fuzzy_typo(self):
        """Faute de frappe dans le CV (developper au lieu de developpeur)."""
        cv_normalized = normalize_for_match("Je suis un developper Python")
        # Doit matcher grâce au fuzzy ou au stem
        self.assertTrue(keyword_matches_text("developpeur", cv_normalized))

    def test_match_multi_token(self):
        cv_normalized = normalize_for_match("Data Engineer senior avec Spark et Kafka")
        self.assertTrue(keyword_matches_text("data engineer", cv_normalized))

    def test_keyword_similarity(self):
        sim = keyword_similarity("Python developer", "senior python developper")
        self.assertGreater(sim, 0.7)


# ─────────────────────────────────────────────────────────────
# Test scénario complet : extraire les vrais critères d'une offre
# ─────────────────────────────────────────────────────────────

class IntegrationSuggestedCriteriaTestCase(SimpleTestCase):
    """Test bout-en-bout : extract_suggested_criteria sur une offre réaliste."""

    def test_full_extraction_data_scientist(self):
        job = _FakeJob(
            title="Senior Data Scientist",
            requirements="""
                - Master ou PhD en informatique, statistiques ou domaine connexe
                - Au moins 5 ans d'expérience en Machine Learning
                - Maîtrise de Python, scikit-learn, TensorFlow ou PyTorch
                - Expérience avec AWS et SQL
                - Connaissance des techniques NLP est un plus
            """,
            description="Vous rejoindrez notre équipe d'IA pour développer des modèles avancés.",
        )
        criteria = extract_suggested_criteria(job)
        # Skills techniques détectés
        self.assertIn("python", criteria["skills"])
        self.assertIn("tensorflow", criteria["skills"])
        self.assertIn("aws", criteria["skills"])
        self.assertIn("sql", criteria["skills"])
        # Niveau d'études
        self.assertIn(criteria["education_level"], ("master", "doctorat"))
        # Expérience
        self.assertEqual(criteria["min_experience"], 5)
        # Keywords non vides
        self.assertGreater(len(criteria["keywords"]), 5)
