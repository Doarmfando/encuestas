"""Handlers de Google Forms separados por tipo de interacción."""
from app.automation.gforms.question_finder import QuestionFinder
from app.automation.gforms.option_clicker import OptionClicker
from app.automation.gforms.text_writer import TextWriter
from app.automation.gforms.dropdown_handler import DropdownHandler
from app.automation.gforms.special_inputs import SpecialInputHandler

__all__ = [
    "QuestionFinder",
    "OptionClicker",
    "TextWriter",
    "DropdownHandler",
    "SpecialInputHandler",
]
