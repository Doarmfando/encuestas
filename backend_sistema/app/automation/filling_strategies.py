"""
Fachada de estrategias compartidas de llenado.
La lógica real vive en app/automation/strategies/.
Para agregar soporte a un nuevo tipo de campo: editar solo el módulo correspondiente.
"""
from app.automation.strategies.text_filler import TextFiller
from app.automation.strategies.option_clicker import OptionClicker
from app.automation.strategies.special_fields import SpecialFieldFiller, _parse_date
from app.automation.strategies.form_utils import FormUtils


class FillingStrategies:
    """Biblioteca de estrategias de llenado — fachada para retrocompatibilidad."""

    # Texto
    fill_text = TextFiller.fill_text
    fill_textarea = TextFiller.fill_textarea
    _fill_text_like_field = TextFiller._fill_text_like_field
    _field_value_matches = TextFiller._field_value_matches

    # Opciones radio/checkbox
    click_option_by_text = OptionClicker.click_option_by_text
    click_multiple_options = OptionClicker.click_multiple_options
    _click_at_index_fallback = OptionClicker._click_at_index_fallback
    _click_locator = OptionClicker._click_locator
    _click_at_index = OptionClicker._click_at_index
    _get_option_texts = OptionClicker._get_option_texts
    _requires_selected_validation = OptionClicker._requires_selected_validation
    _is_control_selected = OptionClicker._is_control_selected

    # Campos especiales
    fill_dropdown = SpecialFieldFiller.fill_dropdown
    fill_date = SpecialFieldFiller.fill_date
    fill_time = SpecialFieldFiller.fill_time
    fill_matrix = SpecialFieldFiller.fill_matrix
    fill_ranking = SpecialFieldFiller.fill_ranking
    _click_in_row = SpecialFieldFiller._click_in_row
    _parse_date = staticmethod(_parse_date)

    # Utilidades
    find_question_container = FormUtils.find_question_container
    auto_detect_and_fill = FormUtils.auto_detect_and_fill
