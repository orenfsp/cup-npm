import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

_SEPARATORS = re.compile(r"[\W_]+", re.UNICODE)
_WHITESPACE = re.compile(r"\s+")


def normalize_crisis_phrase(value: str) -> str:
    """Normalize literal text without accepting administrator-supplied patterns."""

    normalized = unicodedata.normalize("NFKC", value).casefold().replace("ё", "е")
    return _WHITESPACE.sub(" ", _SEPARATORS.sub(" ", normalized)).strip()


def compact_crisis_phrase(value: str) -> str:
    return normalize_crisis_phrase(value).replace(" ", "")


@dataclass(frozen=True, slots=True)
class CrisisRulePattern:
    normalized_phrase: str
    compact_phrase: str
    allow_compact_match: bool = False

    @classmethod
    def from_phrase(cls, phrase: str, *, allow_compact_match: bool = False) -> "CrisisRulePattern":
        return cls(
            normalized_phrase=normalize_crisis_phrase(phrase),
            compact_phrase=compact_crisis_phrase(phrase),
            allow_compact_match=allow_compact_match,
        )


DEFAULT_CRISIS_RULES = (
    CrisisRulePattern.from_phrase("меня бьют"),
    CrisisRulePattern.from_phrase("меня избили"),
    CrisisRulePattern.from_phrase("физическое насилие"),
    CrisisRulePattern.from_phrase("угрожают убить"),
    CrisisRulePattern.from_phrase("угроза моей жизни"),
    CrisisRulePattern.from_phrase("хотят меня убить"),
    CrisisRulePattern.from_phrase("хочу умереть"),
    CrisisRulePattern.from_phrase("не хочу жить", allow_compact_match=True),
    CrisisRulePattern.from_phrase("покончить с собой"),
    CrisisRulePattern.from_phrase("навредить себе"),
    CrisisRulePattern.from_phrase("суицид"),
    CrisisRulePattern.from_phrase("they hit me"),
    CrisisRulePattern.from_phrase("physical violence"),
    CrisisRulePattern.from_phrase("threatened to kill me"),
    CrisisRulePattern.from_phrase("threat to my life"),
    CrisisRulePattern.from_phrase("want to die"),
    CrisisRulePattern.from_phrase("kill myself"),
    CrisisRulePattern.from_phrase("hurt myself"),
)


class CrisisDetector:
    """Deterministic literal matching that retains no match or source text."""

    def __init__(self, rules: Iterable[CrisisRulePattern] = DEFAULT_CRISIS_RULES) -> None:
        self._rules = tuple(rule for rule in rules if rule.normalized_phrase)

    def detect(self, values: Iterable[str | None]) -> bool:
        for value in values:
            if not value:
                continue
            normalized = normalize_crisis_phrase(value)
            padded = f" {normalized} "
            compact = normalized.replace(" ", "")
            for rule in self._rules:
                # Padding keeps literal rules token/boundary aware, including one-word rules.
                if f" {rule.normalized_phrase} " in padded:
                    return True
                if (
                    rule.allow_compact_match
                    and " " in rule.normalized_phrase
                    and rule.compact_phrase in compact
                ):
                    return True
        return False
