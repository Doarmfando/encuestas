"""
Búsqueda del contenedor DOM de una pregunta en Google Forms.
Solo responsabilidad: dado el texto de una pregunta, devolver el listitem correcto.
Para cambiar la estrategia de scoring: solo editar este archivo.
"""
import re
from difflib import SequenceMatcher
from app.automation.gforms._base import normalize_match_text, prepare_scope
from app.automation.timing import pause_action


class QuestionFinder:
    """Encuentra el listitem DOM que corresponde a una pregunta."""

    def find(self, page, pregunta: str, listitems: list, runtime_config: dict | None = None):
        """Retorna el listitem más probable para la pregunta dada, o None."""
        pregunta_norm = normalize_match_text(pregunta, strip_numbering=True)
        if not pregunta_norm:
            return None

        best_item, best_score = self._best_candidate(listitems, pregunta_norm)
        if best_item and best_score >= 350:
            prepare_scope(best_item)
            return best_item

        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            pause_action(runtime_config, multiplier=0.8)
            page.evaluate("window.scrollTo(0, 0)")
            pause_action(runtime_config, multiplier=0.8)
            fresh_items = page.locator('[role="listitem"]').all()
            best_item, best_score = self._best_candidate(fresh_items, pregunta_norm)
            if best_item and best_score >= 350:
                prepare_scope(best_item)
                return best_item
        except Exception:
            pass
        return None

    def score(self, candidate_text: str, target: str) -> int:
        """Puntúa un listitem para elegir la pregunta correcta."""
        candidate = normalize_match_text(candidate_text, strip_numbering=True)
        if not candidate:
            return 0

        lines = [
            normalize_match_text(line, strip_numbering=True)
            for line in str(candidate_text or "").splitlines()
            if line.strip()
        ]
        heading = lines[0] if lines else ""

        score = 0
        if heading == target:
            score += 5000
        if candidate == target:
            score += 4500
        if heading and target in heading:
            score += 3500 + min(len(target), 400)
        if target in candidate:
            score += 3000 + min(len(target), 400)

        sample = heading or candidate[: max(len(target) * 2, 180)]
        score += int(SequenceMatcher(None, target, sample).ratio() * 1200)

        tokens = [tok for tok in re.findall(r"[a-z0-9]+", target) if len(tok) >= 4]
        if tokens:
            common = sum(1 for tok in tokens if tok in candidate)
            score += common * 140
            score += int((common / len(tokens)) * 800)
            if common == len(tokens):
                score += 900
        return score

    def _best_candidate(self, listitems: list, pregunta_norm: str):
        best_item, best_score = None, 0
        for item in listitems:
            try:
                s = self.score(item.inner_text(timeout=1200), pregunta_norm)
                if s > best_score:
                    best_score = s
                    best_item = item
            except Exception:
                continue
        return best_item, best_score
