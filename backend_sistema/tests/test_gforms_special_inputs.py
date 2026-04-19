import unittest
from unittest.mock import patch

from app.automation.gforms.special_inputs import SpecialInputHandler


class FakeControl:
    def __init__(self, label):
        self.label = label
        self.clicked = False

    def get_attribute(self, name):
        if name in {"aria-label", "data-value"}:
            return self.label
        return None  # aria-disabled returns None (not disabled)

    def click(self, force=False):
        self.clicked = True


class FakeLocator:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def count(self):
        return len(self._items)

    @property
    def first(self):
        return self._items[0] if self._items else None


class FakeRow:
    def __init__(self, label, option_labels):
        self.label = label
        self.controls = [FakeControl(option) for option in option_labels]

    def locator(self, selector):
        if '[role="radio"]' in selector or '[role="checkbox"]' in selector:
            return FakeLocator(self.controls)
        return FakeLocator([])

    def get_attribute(self, name):
        if name == "aria-label":
            return self.label
        return ""

    def inner_text(self, timeout=0):
        return self.label


class FakeScope:
    def __init__(self, rows):
        self.rows = rows

    def locator(self, selector):
        if '[role="radiogroup"]' in selector or '[role="group"]' in selector:
            return FakeLocator(self.rows)
        return FakeLocator([])


class GformsSpecialInputsTest(unittest.TestCase):
    @patch("app.automation.gforms.special_inputs.pause_action", return_value=0)
    @patch(
        "app.automation.gforms.special_inputs.click_control",
        side_effect=lambda ctrl, runtime_config=None: ctrl.click() or True,
    )
    def test_fill_matrix_requires_matching_each_row(self, _click_control, _pause):
        rows = [
            FakeRow("Fila A", ["Nunca", "Siempre"]),
            FakeRow("Fila B", ["Nunca", "Siempre"]),
        ]
        handler = SpecialInputHandler()

        ok = handler.fill_matrix(
            page=None,
            valor={"Fila A": "Nunca", "Fila B": "Siempre"},
            tipo="matriz",
            container=FakeScope(rows),
            runtime_config={"timing": {"action_pause_min": 0, "action_pause_max": 0}},
        )

        self.assertTrue(ok)
        self.assertTrue(rows[0].controls[0].clicked)
        self.assertTrue(rows[1].controls[1].clicked)


if __name__ == "__main__":
    unittest.main()
