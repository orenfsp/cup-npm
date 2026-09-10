from app.db.repositories.crisis_rules import CrisisRuleRepository
from app.modules.crisis.detector import CrisisRulePattern


class CrisisRuleService:
    """Loads the small active literal ruleset once per appeal submission."""

    def __init__(self, repository: CrisisRuleRepository) -> None:
        self._repository = repository

    async def active_patterns(self) -> list[CrisisRulePattern]:
        rules = await self._repository.list_active()
        return [
            CrisisRulePattern(
                normalized_phrase=rule.normalized_phrase,
                compact_phrase=rule.compact_phrase,
                allow_compact_match=rule.allow_compact_match,
            )
            for rule in rules
        ]
