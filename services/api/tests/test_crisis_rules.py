from typing import cast

from app.db.models import CrisisRule
from app.db.repositories.crisis_rules import CrisisRuleRepository
from app.modules.crisis.detector import (
    DEFAULT_CRISIS_RULES,
    CrisisDetector,
    CrisisRulePattern,
    compact_crisis_phrase,
    normalize_crisis_phrase,
)
from app.modules.crisis.service import CrisisRuleService
from app.scripts.seed_reference_data import seed_crisis_rules


class FakeCrisisRuleRepository:
    def __init__(self) -> None:
        self.rules: dict[str, CrisisRule] = {}
        self.commits = 0

    async def list_active(self) -> list[CrisisRule]:
        return sorted(
            (rule for rule in self.rules.values() if rule.is_active),
            key=lambda rule: rule.sort_order,
        )

    async def get_by_normalized_phrase(self, phrase: str) -> CrisisRule | None:
        return self.rules.get(phrase)

    async def add(self, rule: CrisisRule) -> None:
        self.rules[rule.normalized_phrase] = rule

    async def commit(self) -> None:
        self.commits += 1


def test_crisis_normalization_handles_case_whitespace_hyphens_and_yo() -> None:
    assert normalize_crisis_phrase("  НЕ   ХОЧУ—ЖИТЬ ") == "не хочу жить"
    assert normalize_crisis_phrase("Всё-ещё") == "все еще"
    detector = CrisisDetector([CrisisRulePattern.from_phrase("не хочу жить")])
    assert detector.detect(["Не хочу жить"])
    assert detector.detect(["не  хочу   жить"])
    assert detector.detect(["не-хочу-жить"])
    assert detector.detect(["не_хочу_жить"])


def test_compact_matching_is_explicit() -> None:
    enabled = CrisisDetector(
        [CrisisRulePattern.from_phrase("не хочу жить", allow_compact_match=True)]
    )
    disabled = CrisisDetector([CrisisRulePattern.from_phrase("не хочу жить")])
    assert enabled.detect(["нехочужить"])
    assert not disabled.detect(["нехочужить"])


def test_single_word_rule_avoids_substring_false_positive() -> None:
    detector = CrisisDetector([CrisisRulePattern.from_phrase("суицид")])
    assert detector.detect(["слово суицид здесь"])
    assert not detector.detect(["несуицидальный контекст"])


async def test_inactive_rules_are_ignored_by_rule_service() -> None:
    repository = FakeCrisisRuleRepository()
    active = CrisisRule(
        phrase="не хочу жить",
        normalized_phrase="не хочу жить",
        compact_phrase="нехочужить",
        is_active=True,
        allow_compact_match=True,
        sort_order=10,
    )
    inactive = CrisisRule(
        phrase="пример",
        normalized_phrase="пример",
        compact_phrase="пример",
        is_active=False,
        allow_compact_match=False,
        sort_order=20,
    )
    repository.rules = {active.normalized_phrase: active, inactive.normalized_phrase: inactive}
    service = CrisisRuleService(cast(CrisisRuleRepository, repository))

    patterns = await service.active_patterns()

    assert [pattern.normalized_phrase for pattern in patterns] == ["не хочу жить"]
    assert not CrisisDetector(patterns).detect(["пример"])


async def test_default_crisis_rules_seed_is_idempotent() -> None:
    repository = FakeCrisisRuleRepository()
    first = await seed_crisis_rules(cast(CrisisRuleRepository, repository))
    second = await seed_crisis_rules(cast(CrisisRuleRepository, repository))

    assert first == (len(DEFAULT_CRISIS_RULES), 0)
    assert second == (0, 0)
    assert len(repository.rules) == len(DEFAULT_CRISIS_RULES)
    assert repository.rules["не хочу жить"].allow_compact_match is True
    assert compact_crisis_phrase("не-хочу-жить") == "нехочужить"

    repository.rules["не хочу жить"].is_active = False
    assert await seed_crisis_rules(cast(CrisisRuleRepository, repository)) == (0, 0)
    assert repository.rules["не хочу жить"].is_active is False
