"""Tests para collect_input_hints centralizado en question_inference."""
import unittest
from unittest.mock import MagicMock


def _make_mock_scope(attrs_list: list[dict]) -> MagicMock:
    """Crea un scope mock con inputs que retornan los attrs dados."""
    scope = MagicMock()
    inputs_locator = MagicMock()
    inputs_locator.count.return_value = len(attrs_list)

    def nth_side_effect(idx):
        el = MagicMock()
        attrs = attrs_list[idx]
        el.get_attribute.side_effect = lambda a: attrs.get(a)
        return el

    inputs_locator.nth.side_effect = nth_side_effect
    scope.locator.return_value = inputs_locator
    return scope


class CollectInputHintsTest(unittest.TestCase):

    def test_returns_empty_string_when_no_inputs(self):
        from app.utils.question_inference import collect_input_hints
        scope = MagicMock()
        scope.locator.return_value.count.return_value = 0
        result = collect_input_hints(scope)
        self.assertEqual(result, "")

    def test_collects_type_attribute(self):
        from app.utils.question_inference import collect_input_hints
        scope = _make_mock_scope([{"type": "number"}])
        result = collect_input_hints(scope)
        self.assertIn("type=number", result)

    def test_joins_multiple_inputs_with_pipe(self):
        from app.utils.question_inference import collect_input_hints
        scope = _make_mock_scope([{"type": "text"}, {"inputmode": "numeric"}])
        result = collect_input_hints(scope)
        self.assertIn(" | ", result)

    def test_respects_max_inputs(self):
        from app.utils.question_inference import collect_input_hints
        scope = _make_mock_scope([{"type": "text"}, {"type": "number"}, {"type": "email"}])
        result = collect_input_hints(scope, max_inputs=2)
        parts = result.split(" | ")
        self.assertLessEqual(len(parts), 2)

    def test_handles_exception_gracefully(self):
        from app.utils.question_inference import collect_input_hints
        scope = MagicMock()
        scope.locator.side_effect = Exception("DOM error")
        result = collect_input_hints(scope)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
