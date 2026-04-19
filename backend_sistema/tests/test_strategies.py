"""Tests para app/automation/strategies/."""
import unittest
from unittest.mock import MagicMock, patch


# ── TextFiller ────────────────────────────────────────────────────────────────

class TextFillerTest(unittest.TestCase):

    def test_field_value_matches_exact(self):
        from app.automation.strategies.text_filler import TextFiller
        self.assertTrue(TextFiller._field_value_matches("hola", "hola"))

    def test_field_value_matches_ignores_spaces(self):
        from app.automation.strategies.text_filler import TextFiller
        self.assertTrue(TextFiller._field_value_matches("hola mundo", "holamundo"))

    def test_field_value_matches_digits_only(self):
        from app.automation.strategies.text_filler import TextFiller
        self.assertTrue(TextFiller._field_value_matches("12,345", "12345"))

    def test_field_value_no_match(self):
        from app.automation.strategies.text_filler import TextFiller
        self.assertFalse(TextFiller._field_value_matches("abc", "xyz"))

    def test_fill_text_returns_false_when_no_visible_input(self):
        from app.automation.strategies.text_filler import TextFiller
        container = MagicMock()
        locator = MagicMock()
        locator.is_visible.return_value = False
        container.locator.return_value.first = locator
        result = TextFiller.fill_text(container, "valor")
        self.assertFalse(result)


# ── OptionClicker ─────────────────────────────────────────────────────────────

class OptionClickerTest(unittest.TestCase):

    def test_returns_false_when_no_options(self):
        from app.automation.strategies.option_clicker import OptionClicker
        container = MagicMock()
        container.locator.return_value.count.return_value = 0
        page = MagicMock()
        result = OptionClicker.click_option_by_text(container, page, "opcion")
        self.assertFalse(result)

    def test_requires_selected_validation_for_radio(self):
        from app.automation.strategies.option_clicker import OptionClicker
        locator = MagicMock()
        locator.get_attribute.side_effect = lambda a: "radio" if a == "type" else None
        self.assertTrue(OptionClicker._requires_selected_validation(locator))

    def test_requires_selected_validation_false_for_text(self):
        from app.automation.strategies.option_clicker import OptionClicker
        locator = MagicMock()
        locator.get_attribute.return_value = "text"
        self.assertFalse(OptionClicker._requires_selected_validation(locator))

    def test_click_multiple_accepts_string_as_list(self):
        from app.automation.strategies.option_clicker import OptionClicker
        container = MagicMock()
        container.locator.return_value.count.return_value = 0
        page = MagicMock()
        result = OptionClicker.click_multiple_options(container, page, "unico_valor")
        self.assertFalse(result)


# ── SpecialFieldFiller ────────────────────────────────────────────────────────

class ParseDateTest(unittest.TestCase):

    def test_parses_yyyy_mm_dd(self):
        from app.automation.strategies.special_fields import _parse_date
        self.assertEqual(_parse_date("2024-03-15"), (15, 3, 2024))

    def test_parses_dd_mm_yyyy(self):
        from app.automation.strategies.special_fields import _parse_date
        self.assertEqual(_parse_date("15-03-2024"), (15, 3, 2024))

    def test_parses_slash_format(self):
        from app.automation.strategies.special_fields import _parse_date
        self.assertEqual(_parse_date("15/03/2024"), (15, 3, 2024))

    def test_returns_none_for_invalid(self):
        from app.automation.strategies.special_fields import _parse_date
        self.assertIsNone(_parse_date("no es fecha"))

    def test_accessible_as_class_method(self):
        from app.automation.strategies.special_fields import SpecialFieldFiller
        self.assertEqual(SpecialFieldFiller._parse_date("2024-01-01"), (1, 1, 2024))


class SpecialFieldFillerTest(unittest.TestCase):

    def test_fill_dropdown_tries_native_select(self):
        from app.automation.strategies.special_fields import SpecialFieldFiller
        container = MagicMock()
        select_mock = MagicMock()
        select_mock.count.return_value = 1
        container.locator.return_value = select_mock
        page = MagicMock()
        SpecialFieldFiller.fill_dropdown(container, page, "opcion")
        select_mock.first.select_option.assert_called_once_with(label="opcion")

    def test_fill_time_parses_hh_mm(self):
        from app.automation.strategies.special_fields import SpecialFieldFiller
        container = MagicMock()
        locator_mock = MagicMock()
        locator_mock.is_visible.return_value = True
        container.locator.return_value.first = locator_mock
        page = MagicMock()
        SpecialFieldFiller.fill_time(container, "14:30", runtime_config=None)
        locator_mock.fill.assert_called()

    def test_fill_date_uses_native_input(self):
        from app.automation.strategies.special_fields import SpecialFieldFiller
        container = MagicMock()
        date_input = MagicMock()
        date_input.is_visible.return_value = True
        container.locator.return_value.first = date_input
        SpecialFieldFiller.fill_date(container, "2024-06-20")
        date_input.fill.assert_called_once_with("2024-06-20")


# ── FillingStrategies facade ──────────────────────────────────────────────────

class FillingStrategiesFacadeTest(unittest.TestCase):

    def test_parse_date_accessible(self):
        from app.automation.filling_strategies import FillingStrategies
        self.assertEqual(FillingStrategies._parse_date("2024-03-15"), (15, 3, 2024))

    def test_field_value_matches_accessible(self):
        from app.automation.filling_strategies import FillingStrategies
        self.assertTrue(FillingStrategies._field_value_matches("abc", "abc"))

    def test_all_public_methods_exist(self):
        from app.automation.filling_strategies import FillingStrategies
        for method in ("fill_text", "fill_textarea", "click_option_by_text",
                       "click_multiple_options", "fill_dropdown", "fill_date",
                       "fill_time", "fill_matrix", "fill_ranking",
                       "find_question_container", "auto_detect_and_fill"):
            self.assertTrue(hasattr(FillingStrategies, method), f"Missing: {method}")


if __name__ == "__main__":
    unittest.main()
