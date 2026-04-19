"""Tests para utilidades de scraping."""
import json
import unittest


class MicrosoftFormsStrategyTest(unittest.TestCase):

    def test_clean_ms_text_removes_nbsp(self):
        from app.scraping.strategies.microsoft_forms import _clean_ms_text
        self.assertEqual(_clean_ms_text("hola\u00a0mundo"), "hola mundo")

    def test_clean_ms_text_none_returns_empty(self):
        from app.scraping.strategies.microsoft_forms import _clean_ms_text
        self.assertEqual(_clean_ms_text(None), "")

    def test_to_num_integer(self):
        from app.scraping.strategies.microsoft_forms import _to_num
        self.assertEqual(_to_num("5.0"), 5)

    def test_to_num_float(self):
        from app.scraping.strategies.microsoft_forms import _to_num
        self.assertAlmostEqual(_to_num("3.5"), 3.5)

    def test_to_num_empty_returns_none(self):
        from app.scraping.strategies.microsoft_forms import _to_num
        self.assertIsNone(_to_num(""))
        self.assertIsNone(_to_num(None))

    def test_order_key_uses_order_field(self):
        from app.scraping.strategies.microsoft_forms import _order_key
        self.assertEqual(_order_key({"order": "2.5"}), 2.5)

    def test_order_key_defaults_to_zero(self):
        from app.scraping.strategies.microsoft_forms import _order_key
        self.assertEqual(_order_key({}), 0)

    def test_parse_qi_dict_passthrough(self):
        from app.scraping.strategies.microsoft_forms import _parse_qi
        qi = {"Choices": ["A", "B"]}
        self.assertEqual(_parse_qi({"questionInfo": qi}), qi)

    def test_parse_qi_string_json(self):
        from app.scraping.strategies.microsoft_forms import _parse_qi
        import json
        qi = {"Choices": ["A"]}
        result = _parse_qi({"questionInfo": json.dumps(qi)})
        self.assertEqual(result, qi)

    def test_parse_qi_invalid_returns_empty(self):
        from app.scraping.strategies.microsoft_forms import _parse_qi
        self.assertEqual(_parse_qi({"questionInfo": "not json"}), {})

    def test_find_api_url_returns_none_for_no_match(self):
        from app.scraping.strategies.microsoft_forms import MicrosoftFormsStrategy
        strategy = MicrosoftFormsStrategy()
        self.assertIsNone(strategy._find_api_url("<html>sin url</html>"))

    def test_extract_choices_from_choices_list(self):
        from app.scraping.strategies.microsoft_forms import MicrosoftFormsStrategy
        strategy = MicrosoftFormsStrategy()
        pregunta = {"opciones": []}
        q = {"choices": [{"description": "Opción A"}, {"description": "Opción B"}]}
        strategy._extract_choices(pregunta, q, {})
        self.assertEqual(pregunta["opciones"], ["Opción A", "Opción B"])


class GoogleFormsNormalizeKeyTest(unittest.TestCase):

    def test_takes_first_line(self):
        from app.scraping.google_forms import GoogleFormsScraper
        s = GoogleFormsScraper()
        result = s._normalize_key("Primera línea\nSegunda línea")
        self.assertNotIn("Segunda", result)

    def test_removes_numbering(self):
        from app.scraping.google_forms import GoogleFormsScraper
        s = GoogleFormsScraper()
        self.assertEqual(s._normalize_key("1. ¿Cuál es tu edad?"), "¿cuál es tu edad?")

    def test_strips_asterisk(self):
        from app.scraping.google_forms import GoogleFormsScraper
        s = GoogleFormsScraper()
        self.assertNotIn("*", s._normalize_key("Pregunta *"))

    def test_truncates_to_60(self):
        from app.scraping.google_forms import GoogleFormsScraper
        s = GoogleFormsScraper()
        long_text = "a" * 100
        self.assertEqual(len(s._normalize_key(long_text)), 60)


def _section_item(item_id: int, title: str):
    return [item_id, title, None, 8, None, None, None, None, None, None, None, [None, title]]


def _choice_item(item_id: int, options: list[str], title: str | None = None):
    return [
        item_id,
        title,
        None,
        2,
        [[item_id + 1000, [[opt, None, None, None, 0] for opt in options], 1, None, None, None, None, None, 0]],
    ]


def _matrix_row(item_id: int, options: list[str], row_text: str, shape: str = "string_list"):
    base_options = [[opt] for opt in options]
    if shape == "string_list":
        return [item_id, base_options, 1, [row_text], None, None, None, None, None, None, None, [0]]
    if shape == "sublist":
        return [item_id, base_options, 1, [[row_text]], None, None, None, None, None, None, None, [0]]
    if shape == "direct_string":
        return [row_text, base_options, 1, None]
    raise ValueError(f"shape desconocido: {shape}")


def _matrix_item(item_id: int, title: str | None, options: list[str], rows: list[tuple[str, str]]):
    return [item_id, title, None, 7, [_matrix_row(item_id + idx + 1, options, row_text, shape) for idx, (row_text, shape) in enumerate(rows)]]


def _fb_payload(items: list) -> list:
    return [None, [None, items]]


def _fb_html(payload: list, title: str = "Formulario de prueba") -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return (
        "<html><head>"
        f'<meta property="og:title" content="{title}">'
        "</head><body>"
        f"<script>var FB_PUBLIC_LOAD_DATA_ = {payload_json};</script>"
        "</body></html>"
    )


class FBDataStrategyNormalizationTest(unittest.TestCase):
    def setUp(self):
        from app.scraping.strategies.fb_data import FBDataStrategy
        self.strategy = FBDataStrategy()
        self.options = ["Nunca", "Rara Vez", "A veces", "Frecuentemente", "Siempre"]

    def test_extract_inherits_section_title_for_titleless_radio(self):
        payload = _fb_payload([
            _section_item(10, "Sexo"),
            _choice_item(20, ["Masculino", "Femenino"], title=None),
        ])

        result = self.strategy.extract(_fb_html(payload, title="Municipio"), "https://docs.google.com/forms/d/e/test/viewform")

        self.assertIsNotNone(result)
        self.assertEqual(result["titulo"], "Municipio")
        self.assertEqual(result["total_preguntas"], 1)
        question = result["paginas"][0]["preguntas"][0]
        self.assertEqual(question["texto"], "Sexo")
        self.assertEqual(question["tipo"], "opcion_multiple")
        self.assertEqual(question["opciones"], ["Masculino", "Femenino"])
        self.assertTrue(question["obligatoria"])

    def test_extract_normalizes_section_backed_matrices_with_multiple_row_shapes(self):
        payload = _fb_payload([
            _section_item(10, "Sexo"),
            _choice_item(20, ["Masculino", "Femenino"], title=None),
            _matrix_item(
                30,
                "Sección 1: Estabilidad y Calidad del Voltaje",
                self.options,
                [
                    ("Noto que las luces parpadean.", "string_list"),
                    ("Se me han quemado bombillos.", "string_list"),
                ],
            ),
            _section_item(40, "Sección 2: Interrupciones y Apagones"),
            _matrix_item(
                50,
                None,
                self.options,
                [
                    ("Se va la luz sin previo aviso.", "sublist"),
                    ("Los apagones duran más de 4 horas.", "sublist"),
                ],
            ),
            _section_item(60, "Sección 3: Infraestructura y Seguridad en el Sector"),
            _matrix_item(
                70,
                None,
                self.options,
                [
                    ("Veo cables caídos en mi comunidad.", "direct_string"),
                    ("El transformador hace ruidos fuertes.", "direct_string"),
                ],
            ),
        ])

        result = self.strategy.extract(_fb_html(payload), "https://docs.google.com/forms/d/e/test/viewform")

        self.assertIsNotNone(result)
        self.assertEqual(result["total_preguntas"], 4)
        self.assertEqual(len(result["paginas"]), 4)

        preguntas = [pagina["preguntas"][0] for pagina in result["paginas"]]
        self.assertEqual(preguntas[0]["texto"], "Sexo")
        self.assertEqual(preguntas[1]["texto"], "Sección 1: Estabilidad y Calidad del Voltaje")
        self.assertEqual(preguntas[2]["texto"], "Sección 2: Interrupciones y Apagones")
        self.assertEqual(preguntas[3]["texto"], "Sección 3: Infraestructura y Seguridad en el Sector")

        for pregunta in preguntas[1:]:
            self.assertEqual(pregunta["tipo"], "matriz")
            self.assertEqual(pregunta["opciones"], self.options)
            self.assertGreaterEqual(len(pregunta.get("filas", [])), 2)

        self.assertEqual(
            preguntas[1]["filas"],
            ["Noto que las luces parpadean.", "Se me han quemado bombillos."],
        )
        self.assertEqual(
            preguntas[2]["filas"],
            ["Se va la luz sin previo aviso.", "Los apagones duran más de 4 horas."],
        )
        self.assertEqual(
            preguntas[3]["filas"],
            ["Veo cables caídos en mi comunidad.", "El transformador hace ruidos fuertes."],
        )
        self.assertTrue(all(q["texto"].strip() for q in preguntas))


class GoogleFormsStrategySelectionTest(unittest.TestCase):
    def test_prefers_complete_fb_result_over_incomplete_playwright(self):
        from app.scraping.google_forms import GoogleFormsScraper

        scraper = GoogleFormsScraper()
        fb_result = {
            "url": "https://docs.google.com/forms/d/e/test/viewform",
            "titulo": "Municipio",
            "descripcion": "",
            "paginas": [
                {
                    "numero": 1,
                    "preguntas": [
                        {
                            "texto": "Sexo",
                            "tipo": "opcion_multiple",
                            "obligatoria": True,
                            "opciones": ["Masculino", "Femenino"],
                        }
                    ],
                    "botones": ["Enviar"],
                }
            ],
            "total_preguntas": 1,
            "requiere_login": False,
            "plataforma": "google_forms",
        }
        pw_result = {
            "url": "https://docs.google.com/forms/d/e/test/viewform",
            "titulo": "Municipio",
            "descripcion": "",
            "paginas": [
                {
                    "numero": 1,
                    "preguntas": [
                        {
                            "texto": "",
                            "tipo": "matriz",
                            "obligatoria": False,
                            "opciones": [],
                            "filas": [],
                        }
                    ],
                    "botones": ["Enviar"],
                }
            ],
            "total_preguntas": 1,
            "requiere_login": False,
            "plataforma": "google_forms",
        }

        result = scraper._combinar_estrategias(
            fb_result,
            pw_result,
            "<html></html>",
            scraper.resultado_vacio("https://docs.google.com/forms/d/e/test/viewform", "google_forms"),
        )

        self.assertTrue(scraper._is_structurally_complete(result))
        self.assertEqual(result["paginas"][0]["preguntas"][0]["texto"], "Sexo")
        self.assertEqual(result["paginas"][0]["preguntas"][0]["opciones"], ["Masculino", "Femenino"])


if __name__ == "__main__":
    unittest.main()
