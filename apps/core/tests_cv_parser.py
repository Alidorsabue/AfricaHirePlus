"""
Tests unitaires du parser CV (apps.core.cv_parser).
Vérifie l'extraction des skills, expérience, éducation, langues depuis du texte brut.
"""
from django.test import SimpleTestCase

from apps.core.cv_parser import (
    ParsedCV,
    extract_contact_info,
    extract_education_level,
    extract_experience_years,
    extract_languages,
    extract_skills,
    parse_cv,
)


CV_DEV_FR = """
Jean Dupont
Développeur Python senior
jean.dupont@example.com | +33 6 12 34 56 78

EXPÉRIENCE PROFESSIONNELLE
2018 - 2024 : Lead Developer Python @ TechCorp
  - Conception d'API REST avec Django et FastAPI
  - Déploiement sur AWS (EC2, S3, Lambda) avec Terraform et Docker
2014 - 2018 : Backend Developer @ StartupXYZ
  - Stack : Python, PostgreSQL, Redis, Celery

FORMATION
2014 : Master 2 Informatique - Université Paris-Saclay
2012 : Licence Mathématiques-Informatique

COMPÉTENCES
Python, Django, FastAPI, PostgreSQL, AWS, Docker, Kubernetes, Git, REST API, CI/CD

LANGUES
Français : langue maternelle
Anglais : courant (C1)
Espagnol : intermédiaire
"""

CV_DATA_EN = """
Marie Curie
Senior Data Scientist - 8+ years of experience
marie@example.com | +1 555 0100

PROFESSIONAL EXPERIENCE
2016 to 2024 : Senior Data Scientist at GlobalAI
  - Built ML pipelines with Python, PyTorch, and TensorFlow
  - Productionized models on Azure and GCP

EDUCATION
PhD in Machine Learning - MIT
MSc in Statistics - Stanford

SKILLS
Python, R, SQL, PyTorch, TensorFlow, scikit-learn, Pandas, Spark, Tableau, Power BI

LANGUAGES
English (native), French (fluent), Spanish (basic)
"""

CV_NOISY = "Quelques mots sans structure. Un peu de texte."


class ExtractSkillsTestCase(SimpleTestCase):
    """Détection des compétences via le référentiel TECH_SKILLS."""

    def test_extract_skills_from_fr_cv(self):
        skills, conf = extract_skills(CV_DEV_FR)
        self.assertIn("python", skills)
        self.assertIn("django", skills)
        self.assertIn("aws", skills)
        self.assertIn("docker", skills)
        self.assertIn("kubernetes", skills)
        self.assertGreater(conf, 0.5)

    def test_extract_skills_from_en_cv(self):
        skills, conf = extract_skills(CV_DATA_EN)
        self.assertIn("python", skills)
        self.assertIn("pytorch", skills)
        self.assertIn("tensorflow", skills)
        self.assertIn("spark", skills)
        self.assertGreater(conf, 0.5)

    def test_short_acronyms_not_lost(self):
        """Les sigles 2-3 lettres importants doivent être détectés (R, SQL, AWS, ML)."""
        skills, _ = extract_skills(CV_DATA_EN)
        self.assertIn("sql", skills)
        # 'r' est dans TECH_SKILLS mais doit être détecté seulement avec délimiteur
        # ici "R" majuscule dans la section skills

    def test_extract_skills_empty(self):
        skills, conf = extract_skills("")
        self.assertEqual(skills, [])
        self.assertEqual(conf, 0.0)


class ExtractExperienceTestCase(SimpleTestCase):
    """Détection des années d'expérience."""

    def test_direct_phrase_french(self):
        text = "Développeur Python avec 8 ans d'expérience dans le web."
        years, conf = extract_experience_years(text)
        self.assertEqual(years, 8)
        self.assertGreater(conf, 0.7)

    def test_plus_notation(self):
        text = "Senior Data Scientist - 10+ years of experience"
        years, conf = extract_experience_years(text)
        self.assertEqual(years, 10)

    def test_period_aggregation(self):
        """Si pas de phrase explicite, agréger les périodes de la section expérience."""
        text = """
        EXPERIENCE
        2018 - 2024 : Lead Dev
        2014 - 2018 : Backend Dev
        """
        years, _conf = extract_experience_years(text)
        # 6 ans + 4 ans = 10 ans
        self.assertIsNotNone(years)
        self.assertGreaterEqual(years, 8)

    def test_no_experience_returns_none(self):
        years, conf = extract_experience_years("Pas de mention de durée.")
        self.assertIsNone(years)
        self.assertEqual(conf, 0.0)


class ExtractEducationTestCase(SimpleTestCase):
    """Détection du niveau d'études."""

    def test_master_fr(self):
        level, conf = extract_education_level(CV_DEV_FR)
        self.assertEqual(level, "master")
        self.assertGreater(conf, 0.5)

    def test_phd_en(self):
        level, conf = extract_education_level(CV_DATA_EN)
        self.assertEqual(level, "doctorat")

    def test_no_education(self):
        level, conf = extract_education_level("Texte sans niveau d'études.")
        self.assertIsNone(level)
        self.assertEqual(conf, 0.0)


class ExtractLanguagesTestCase(SimpleTestCase):
    """Détection des langues + niveaux."""

    def test_extract_fr_cv(self):
        langs, conf = extract_languages(CV_DEV_FR)
        names = {l["language"] for l in langs}
        self.assertIn("français", names)
        self.assertIn("anglais", names)
        self.assertIn("espagnol", names)
        self.assertGreater(conf, 0.5)

    def test_extract_en_cv(self):
        langs, _conf = extract_languages(CV_DATA_EN)
        names = {l["language"] for l in langs}
        self.assertIn("anglais", names)
        self.assertIn("français", names)

    def test_level_detection(self):
        langs, _conf = extract_languages(CV_DEV_FR)
        for l in langs:
            if l["language"] == "français":
                self.assertEqual(l["proficiency"], "natif")
            if l["language"] == "anglais":
                self.assertEqual(l["proficiency"], "courant")


class ExtractContactInfoTestCase(SimpleTestCase):
    """Détection emails et téléphones."""

    def test_email_extraction(self):
        emails, _ = extract_contact_info(CV_DEV_FR)
        self.assertIn("jean.dupont@example.com", emails)

    def test_phone_extraction(self):
        _, phones = extract_contact_info(CV_DEV_FR)
        self.assertGreater(len(phones), 0)


class ParseCvOrchestratorTestCase(SimpleTestCase):
    """Pipeline complet parse_cv."""

    def test_full_parse_fr(self):
        parsed = parse_cv(CV_DEV_FR)
        self.assertIsInstance(parsed, ParsedCV)
        self.assertGreater(len(parsed.skills), 5)
        self.assertEqual(parsed.education_level, "master")
        self.assertGreater(len(parsed.languages), 0)
        self.assertEqual(len(parsed.emails), 1)

    def test_full_parse_en(self):
        parsed = parse_cv(CV_DATA_EN)
        self.assertGreater(len(parsed.skills), 5)
        self.assertEqual(parsed.education_level, "doctorat")

    def test_empty_text_returns_warnings(self):
        parsed = parse_cv("")
        self.assertEqual(parsed.skills, [])
        self.assertGreater(len(parsed.warnings), 0)

    def test_noisy_text_does_not_crash(self):
        parsed = parse_cv(CV_NOISY)
        # Le parser doit retourner un résultat (potentiellement vide) sans planter
        self.assertIsInstance(parsed, ParsedCV)
