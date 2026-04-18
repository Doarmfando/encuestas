"""Tests para app/utils/fuzzy_matcher.py"""
import unittest
from app.utils.fuzzy_matcher import similarity, find_best_match, map_keys_fuzzy


class SimilarityTest(unittest.TestCase):
    def test_identical_strings(self):
        self.assertAlmostEqual(similarity("hola", "hola"), 1.0)

    def test_totally_different(self):
        self.assertLess(similarity("xyz", "abc"), 0.5)

    def test_accent_insensitive(self):
        self.assertGreater(similarity("genero", "género"), 0.9)

    def test_partial_match(self):
        score = similarity("edad", "¿Cuál es tu edad?")
        self.assertGreater(score, 0.3)


class FindBestMatchTest(unittest.TestCase):
    CANDIDATOS = ["Edad", "Sexo", "Ocupación", "Estado Civil"]

    def test_exact_match(self):
        result = find_best_match("Edad", self.CANDIDATOS)
        self.assertEqual(result, "Edad")

    def test_accent_variant(self):
        result = find_best_match("Ocupacion", self.CANDIDATOS)
        self.assertEqual(result, "Ocupación")

    def test_below_threshold_returns_none(self):
        result = find_best_match("Temperatura", self.CANDIDATOS, threshold=0.7)
        self.assertIsNone(result)

    def test_empty_candidatos(self):
        self.assertIsNone(find_best_match("hola", []))

    def test_empty_texto(self):
        self.assertIsNone(find_best_match("", self.CANDIDATOS))

    def test_custom_threshold(self):
        result = find_best_match("edad", self.CANDIDATOS, threshold=0.5)
        self.assertIsNotNone(result)


class MapKeysFuzzyTest(unittest.TestCase):
    def test_exact_keys_preserved(self):
        source = {"Hombre": 60, "Mujer": 40}
        targets = ["Hombre", "Mujer"]
        result = map_keys_fuzzy(source, targets)
        self.assertEqual(result["Hombre"], 60)
        self.assertEqual(result["Mujer"], 40)

    def test_accent_correction(self):
        source = {"Genero masculino": 70, "Genero femenino": 30}
        targets = ["Género masculino", "Género femenino"]
        result = map_keys_fuzzy(source, targets)
        self.assertIn("Género masculino", result)
        self.assertIn("Género femenino", result)

    def test_no_match_keeps_original_key(self):
        source = {"XYZ_INVENTADO": 100}
        targets = ["Hombre", "Mujer"]
        result = map_keys_fuzzy(source, targets, threshold=0.9)
        self.assertIn("XYZ_INVENTADO", result)

    def test_values_preserved(self):
        source = {"Si": 80, "No": 20}
        targets = ["Sí", "No"]
        result = map_keys_fuzzy(source, targets)
        total = sum(result.values())
        self.assertEqual(total, 100)

    def test_empty_source(self):
        self.assertEqual(map_keys_fuzzy({}, ["a", "b"]), {})

    def test_empty_targets(self):
        source = {"hola": 100}
        result = map_keys_fuzzy(source, [])
        self.assertEqual(result, source)


if __name__ == "__main__":
    unittest.main()
