"""
Tests unitaires du moteur d'extraction de CV v2 (apps.core.cv_extraction).
Couvre : détection de format, nettoyage, score qualité, fallback,
rétro-compatibilité de l'API v1.
"""
from io import BytesIO

from django.test import SimpleTestCase

from apps.core.cv_extraction import (
    ExtractionMethod,
    ExtractionResult,
    extract_cv,
    extract_text_from_uploaded_file,
    _clean_text,
    _detect_format,
    _quality_score,
)


class FormatDetectionTestCase(SimpleTestCase):
    """La détection doit privilégier les magic bytes, puis l'extension, puis le content_type."""

    def test_detect_pdf_by_magic_bytes(self):
        self.assertEqual(_detect_format("cv", "", b"%PDF-1.4\n"), "pdf")

    def test_detect_docx_by_magic_bytes(self):
        # PK\x03\x04 = signature ZIP (docx/odt)
        self.assertEqual(_detect_format("cv.docx", "", b"PK\x03\x04"), "docx")

    def test_detect_odt_vs_docx_via_extension(self):
        """Même magic ZIP : l'extension départage docx et odt."""
        self.assertEqual(_detect_format("doc.odt", "", b"PK\x03\x04"), "odt")
        self.assertEqual(_detect_format("doc.docx", "", b"PK\x03\x04"), "docx")

    def test_detect_png_by_magic_bytes(self):
        self.assertEqual(_detect_format("img", "", b"\x89PNG\r\n\x1a\n"), "png")

    def test_detect_jpg_by_magic_bytes(self):
        self.assertEqual(_detect_format("img", "", b"\xff\xd8\xff\xe0"), "jpg")

    def test_detect_by_extension_when_no_magic(self):
        self.assertEqual(_detect_format("cv.txt", "", b"hello"), "txt")
        self.assertEqual(_detect_format("cv.RTF", "", b""), "rtf")

    def test_detect_by_content_type_fallback(self):
        self.assertEqual(_detect_format("file", "application/pdf", b""), "pdf")
        self.assertEqual(
            _detect_format("file", "application/vnd.oasis.opendocument.text", b""),
            "odt",
        )
        self.assertEqual(_detect_format("file", "image/webp", b""), "webp")

    def test_detect_unknown(self):
        self.assertEqual(_detect_format("noidea", "application/x-bin", b"\x00\x01\x02"), "unknown")


class CleanTextTestCase(SimpleTestCase):
    """Nettoyage Unicode + suppression artefacts PDF."""

    def test_collapses_multiple_spaces(self):
        self.assertEqual(_clean_text("hello     world"), "hello world")

    def test_normalizes_nbsp_and_zwsp(self):
        self.assertNotIn("\u00a0", _clean_text("a\u00a0b\u200bc"))

    def test_strips_isolated_page_numbers(self):
        result = _clean_text("page 1 contenu\n\n42\n\npage 2 contenu")
        self.assertNotIn("\n42\n", result)

    def test_collapses_excessive_blank_lines(self):
        result = _clean_text("a\n\n\n\n\nb")
        self.assertEqual(result, "a\n\nb")

    def test_em_dash_normalized(self):
        self.assertEqual(_clean_text("a \u2014 b"), "a - b")

    def test_empty_input(self):
        self.assertEqual(_clean_text(""), "")
        self.assertEqual(_clean_text(None), "")  # type: ignore[arg-type]


class QualityScoreTestCase(SimpleTestCase):
    """Score qualité 0–1 calibré sur ratio lettres / longueur / absence de garbage."""

    def test_empty_text_score_zero(self):
        self.assertEqual(_quality_score(""), 0.0)

    def test_very_short_text_score_zero(self):
        self.assertEqual(_quality_score("ab"), 0.0)

    def test_clean_long_text_high_score(self):
        text = "Un CV complet avec beaucoup de texte naturel. " * 60
        self.assertGreater(_quality_score(text), 0.6)

    def test_garbage_penalty(self):
        garbage = "\ufffd\ufffd\ufffd\ufffd\u25a1???" * 30
        self.assertLess(_quality_score(garbage), 0.3)


class ExtractionResultTestCase(SimpleTestCase):
    """Comportement du dataclass ExtractionResult."""

    def test_is_sufficient_true(self):
        r = ExtractionResult(text="x" * 150)
        self.assertTrue(r.is_sufficient)

    def test_is_sufficient_false(self):
        r = ExtractionResult(text="trop court")
        self.assertFalse(r.is_sufficient)

    def test_to_dict_shape(self):
        r = ExtractionResult(
            text="hello world " * 10,
            method=ExtractionMethod.PYPDF,
            page_count=2,
            quality_score=0.85,
            ocr_used=False,
            warnings=["w1"],
        )
        d = r.to_dict()
        self.assertEqual(d["method"], "pypdf")
        self.assertEqual(d["page_count"], 2)
        self.assertEqual(d["quality_score"], 0.85)
        self.assertFalse(d["ocr_used"])
        self.assertEqual(d["warnings"], ["w1"])
        self.assertGreater(d["char_count"], 0)


class ExtractCvTxtTestCase(SimpleTestCase):
    """Pipeline complet sur du texte brut (pas de dépendance externe)."""

    def test_extract_plain_text_utf8(self):
        content = "Jean Dupont\nDéveloppeur Python\n5 ans d'expérience en Django.\n" * 5
        buf = BytesIO(content.encode("utf-8"))
        result = extract_cv(buf, filename="cv.txt", content_type="text/plain")
        self.assertEqual(result.method, ExtractionMethod.PLAIN_TEXT)
        self.assertIn("Jean Dupont", result.text)
        self.assertGreater(result.quality_score, 0)

    def test_extract_plain_text_utf8_bom(self):
        content = "\ufeffCandidat avec BOM\n" * 10
        buf = BytesIO(content.encode("utf-8-sig"))
        result = extract_cv(buf, filename="cv.txt")
        self.assertNotIn("\ufeff", result.text)

    def test_extract_plain_text_latin1_fallback(self):
        content = "Café avec accents éàïô".encode("latin-1") * 10
        buf = BytesIO(content)
        result = extract_cv(buf, filename="cv.txt")
        self.assertEqual(result.method, ExtractionMethod.PLAIN_TEXT)
        self.assertGreater(len(result.text), 0)

    def test_extract_empty_file(self):
        result = extract_cv(b"", filename="cv.txt")
        self.assertEqual(result.method, ExtractionMethod.NONE)
        self.assertIn("Fichier vide ou illisible.", result.warnings)

    def test_extract_unknown_format(self):
        result = extract_cv(b"\x01\x02\x03\x04", filename="cv.xyz", content_type="application/octet-stream")
        self.assertEqual(result.method, ExtractionMethod.NONE)
        self.assertTrue(any("non supporté" in w for w in result.warnings))


class BackwardCompatibilityTestCase(SimpleTestCase):
    """L'API v1 (extract_text_from_uploaded_file) doit continuer à retourner une str."""

    def test_returns_string(self):
        class FakeUpload:
            name = "cv.txt"
            content_type = "text/plain"

            def __init__(self, data: bytes):
                self._buf = BytesIO(data)

            def read(self):
                return self._buf.read()

            def seek(self, pos: int):
                self._buf.seek(pos)

        upload = FakeUpload("Curriculum Vitae complet de Jean Dupont.\n".encode("utf-8") * 5)
        text = extract_text_from_uploaded_file(upload)
        self.assertIsInstance(text, str)
        self.assertIn("Jean Dupont", text)

    def test_returns_empty_string_for_none(self):
        self.assertEqual(extract_text_from_uploaded_file(None), "")
