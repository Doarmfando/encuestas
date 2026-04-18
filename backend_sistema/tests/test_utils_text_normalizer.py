"""Tests para app/utils/text_normalizer.py"""
import unittest
from app.utils.text_normalizer import normalize, normalize_for_matching, normalize_for_key


class NormalizeTest(unittest.TestCase):
    def test_lowercase(self):
        self.assertEqual(normalize("HOLA"), "hola")

    def test_strip_whitespace(self):
        self.assertEqual(normalize("  hola  "), "hola")

    def test_remove_accents(self):
        self.assertEqual(normalize("Ángel"), "angel")

    def test_tilde_on_vowels(self):
        self.assertEqual(normalize("niño"), "nino")

    def test_empty_string(self):
        self.assertEqual(normalize(""), "")

    def test_none_like_empty(self):
        self.assertEqual(normalize(None), "")

    def test_keep_accents_when_disabled(self):
        # Con remove_accents=False el acento se mantiene (en forma NFKD descompuesta)
        result = normalize("Ángel", remove_accents=False, lowercase=True)
        # La forma descompuesta tiene el carácter base 'a' más el combining accent
        import unicodedata
        has_combining = any(unicodedata.combining(ch) for ch in result)
        self.assertTrue(has_combining, "Se esperan combining chars cuando remove_accents=False")

    def test_keep_case_when_disabled(self):
        result = normalize("HOLA", lowercase=False)
        self.assertEqual(result, "HOLA")


class NormalizeForMatchingTest(unittest.TestCase):
    def test_strips_trailing_punctuation(self):
        self.assertEqual(normalize_for_matching("hola:"), "hola")
        self.assertEqual(normalize_for_matching("hola*"), "hola")
        self.assertEqual(normalize_for_matching("hola."), "hola")

    def test_collapses_spaces(self):
        self.assertEqual(normalize_for_matching("hola   mundo"), "hola mundo")

    def test_removes_accents(self):
        self.assertEqual(normalize_for_matching("Género"), "genero")

    def test_equivalence_with_accent_variants(self):
        self.assertEqual(
            normalize_for_matching("¿Cuál es tu edad?"),
            normalize_for_matching("¿Cual es tu edad?"),
        )


class NormalizeForKeyTest(unittest.TestCase):
    def test_removes_special_chars(self):
        result = normalize_for_key("¿Cuál es tu sexo?")
        self.assertNotIn("¿", result)
        self.assertNotIn("?", result)

    def test_collapses_spaces(self):
        result = normalize_for_key("hola   mundo")
        self.assertEqual(result, "hola mundo")

    def test_alphanumeric_only(self):
        result = normalize_for_key("hello-world!")
        self.assertNotIn("-", result)
        self.assertNotIn("!", result)


if __name__ == "__main__":
    unittest.main()
