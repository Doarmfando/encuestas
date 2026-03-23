"""
Esperas dirigidas por estado del DOM para navegacion entre paginas.
"""
import hashlib
import time

from app.automation.navigation.selectors import GENERIC, detectar_plataforma
from app.automation.timing import get_poll_interval, get_timeout_ms, pause_settle

READY_SELECTORS = {
    "google_forms": ['[role="listitem"]', '[role="heading"]', 'form'],
    "microsoft_forms": ['#question-list', 'form'],
    "typeform": ['form', '[role="button"]', 'textarea, input'],
    "generic": ['form', 'input, textarea, select, [role="radio"], [role="checkbox"], [role="listbox"]'],
}

INTERACTIVE_SELECTOR = (
    'input:not([type="hidden"]), textarea, select, [role="radio"], [role="checkbox"], '
    '[role="listbox"], [role="button"], button'
)
QUESTION_SELECTOR = '[role="listitem"]'
VALIDATION_TEXTS = (
    "esta pregunta es obligatoria",
    "this is a required question",
    "pregunta obligatoria",
)


def wait_for_form_ready(page, url: str = "", runtime_config: dict | None = None) -> bool:
    """Espera a que haya una señal clara de formulario listo."""
    platform = detectar_plataforma(url) if url else GENERIC
    selectors = READY_SELECTORS.get(platform["name"], READY_SELECTORS["generic"])
    timeout_ms = get_timeout_ms(runtime_config, "ready_wait_timeout_s")
    per_selector_timeout = max(int(timeout_ms / max(len(selectors), 1)), 800)

    try:
        page.wait_for_load_state("domcontentloaded")
    except Exception:
        pass

    for selector in selectors:
        try:
            page.wait_for_selector(selector, timeout=per_selector_timeout)
            pause_settle(runtime_config, multiplier=0.6)
            return True
        except Exception:
            continue

    pause_settle(runtime_config, multiplier=0.5)
    return False


def capture_page_state(page, url: str = "") -> dict:
    """Toma un snapshot liviano para detectar cambios de pagina o confirmacion."""
    platform = detectar_plataforma(url) if url else GENERIC
    content = _safe_page_content(page).lower()
    question_titles = _extract_question_titles(page)

    return {
        "url": _safe_attr(lambda: page.url, ""),
        "interactive_count": _safe_count(page, INTERACTIVE_SELECTOR),
        "next_visible": _has_visible_button(page, platform.get("next_texts", [])),
        "submit_visible": _has_visible_button(page, platform.get("submit_texts", [])),
        "question_signature": (
            hashlib.md5("|".join(question_titles).encode("utf-8", errors="ignore")).hexdigest()
            if question_titles else ""
        ),
        "question_count": len(question_titles),
        "validation_visible": any(text in content for text in VALIDATION_TEXTS),
        "content_hash": hashlib.md5(content[:4000].encode("utf-8", errors="ignore")).hexdigest() if content else "",
    }


def wait_for_post_action(
    page,
    before_state: dict | None,
    url: str = "",
    runtime_config: dict | None = None,
    after_submit: bool = False,
) -> bool:
    """Espera cambios perceptibles tras hacer click en siguiente/enviar."""
    baseline = before_state or capture_page_state(page, url)
    wait_key = "submit_confirm_timeout_s" if after_submit else "nav_wait_timeout_s"
    timeout_s = max(get_timeout_ms(runtime_config, wait_key) / 1000.0, 0.2)
    poll_interval = get_poll_interval(runtime_config)
    deadline = time.perf_counter() + timeout_s

    while time.perf_counter() < deadline:
        if after_submit and has_success_signal(page, url, submit_clicked=True):
            pause_settle(runtime_config, multiplier=0.5)
            return True

        current = capture_page_state(page, url)
        if current["url"] != baseline["url"]:
            pause_settle(runtime_config, multiplier=0.5)
            return True
        if (
            current["question_signature"]
            and baseline["question_signature"]
            and current["question_signature"] != baseline["question_signature"]
        ):
            pause_settle(runtime_config, multiplier=0.5)
            return True
        if (
            not current["question_signature"]
            and not baseline["question_signature"]
            and current["content_hash"]
            and current["content_hash"] != baseline["content_hash"]
        ):
            pause_settle(runtime_config, multiplier=0.5)
            return True
        if (
            current["interactive_count"] != baseline["interactive_count"]
            and current["question_signature"] != baseline["question_signature"]
        ):
            pause_settle(runtime_config, multiplier=0.5)
            return True
        if (
            current["next_visible"] != baseline["next_visible"]
            and current["question_signature"] != baseline["question_signature"]
        ):
            pause_settle(runtime_config, multiplier=0.5)
            return True
        if (
            current["submit_visible"] != baseline["submit_visible"]
            and current["question_signature"] != baseline["question_signature"]
        ):
            pause_settle(runtime_config, multiplier=0.5)
            return True

        time.sleep(poll_interval)

    return False


def wait_for_submission_signal(
    page,
    url: str = "",
    runtime_config: dict | None = None,
    submit_clicked: bool = False,
) -> bool:
    """Espera confirmacion de envio usando señales de URL, DOM y textos."""
    if has_success_signal(page, url, submit_clicked=submit_clicked):
        pause_settle(runtime_config, multiplier=0.5)
        return True

    timeout_s = max(get_timeout_ms(runtime_config, "submit_confirm_timeout_s") / 1000.0, 0.2)
    poll_interval = get_poll_interval(runtime_config)
    deadline = time.perf_counter() + timeout_s

    while time.perf_counter() < deadline:
        time.sleep(poll_interval)
        if has_success_signal(page, url, submit_clicked=submit_clicked):
            pause_settle(runtime_config, multiplier=0.5)
            return True

    return has_success_signal(page, url, submit_clicked=submit_clicked)


def has_success_signal(page, url: str = "", submit_clicked: bool = False) -> bool:
    """Detecta una señal clara de exito tras enviar el formulario."""
    platform = detectar_plataforma(url) if url else GENERIC
    page_url = _safe_attr(lambda: page.url, "")

    for pattern in platform.get("success_url_patterns", []):
        if pattern and pattern in page_url:
            return True

    content = _safe_page_content(page).lower()
    for text in platform.get("success_texts", []):
        if text and text.lower() in content:
            return True

    if platform.get("name") == "microsoft_forms":
        if _safe_count(
            page,
            '[class*="thank"], [class*="confirmation"], '
            '[data-automation-id="thankYouMessage"], [class*="post-submit"]',
        ) > 0:
            return True
        return False

    if not submit_clicked:
        return False

    submit_visible = _has_visible_button(page, platform.get("submit_texts", ["Enviar", "Submit"]))
    next_visible = _has_visible_button(page, platform.get("next_texts", ["Siguiente", "Next"]))
    interactivos = _safe_count(
        page,
        '[role="listitem"], input:not([type="hidden"]), textarea, [role="radio"], '
        '[role="checkbox"], [role="listbox"]',
    )
    return not submit_visible and not next_visible and interactivos == 0


def _has_visible_button(page, texts: list[str]) -> bool:
    for text in texts:
        if not text:
            continue
        selector = (
            f'[role="button"]:has-text("{text}"), '
            f'button:has-text("{text}"), input[type="submit"][value="{text}"]'
        )
        try:
            locator = page.locator(selector)
            total = _safe_attr(locator.count, 0)
            for idx in range(total):
                try:
                    if locator.nth(idx).is_visible(timeout=200):
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def _safe_page_content(page) -> str:
    return _safe_attr(lambda: page.content(), "")


def _safe_count(page, selector: str) -> int:
    try:
        return page.locator(selector).count()
    except Exception:
        return 0


def _safe_attr(getter, default):
    try:
        return getter()
    except Exception:
        return default


def _extract_question_titles(page, limit: int = 8) -> list[str]:
    titles = []
    try:
        items = page.locator(QUESTION_SELECTOR).all()
    except Exception:
        return titles

    for item in items:
        if len(titles) >= limit:
            break
        try:
            if hasattr(item, "is_visible") and not item.is_visible(timeout=100):
                continue
            title = _extract_question_title(item.inner_text(timeout=400))
            if title:
                titles.append(title)
        except Exception:
            continue
    return titles


def _extract_question_title(raw_text: str) -> str:
    for line in str(raw_text or "").splitlines():
        clean = " ".join(line.replace("*", " ").split()).strip()
        if not clean:
            continue
        if clean.lower() in VALIDATION_TEXTS:
            continue
        return clean[:160]
    return ""
