from uuid import UUID

from app.db.models.enums import StaffRole
from app.db.repositories.operator import OperatorRepository
from app.modules.operator.schemas import RoutingCandidate, RoutingRecommendation


class RoutingService:
    """Deterministic category/group/capacity recommendation; never assigns."""

    def __init__(self, repository: OperatorRepository) -> None:
        self._repository = repository

    async def recommend(self, category_id: UUID | None) -> RoutingRecommendation:
        if category_id is None:
            return RoutingRecommendation(
                state="category_required",
                recommended_expert=None,
                candidates=[],
                reason="Select a category before requesting a routing recommendation.",
            )
        records = await self._repository.routing_candidates(category_id)
        grouped: dict[UUID, RoutingCandidate] = {}
        for record in records:
            if (
                not record.staff.is_active
                or record.staff.role is not StaffRole.EXPERT
                or not record.group.is_active
            ):
                continue
            candidate = grouped.get(record.staff.id)
            if candidate is None:
                grouped[record.staff.id] = RoutingCandidate(
                    expert_id=record.staff.id,
                    display_name=record.staff.display_name,
                    groups=[record.group.name],
                    current_load=record.current_load,
                    capacity=record.profile.max_active_appeals,
                    available=record.current_load < record.profile.max_active_appeals,
                )
            elif record.group.name not in candidate.groups:
                candidate.groups.append(record.group.name)

        candidates = sorted(
            grouped.values(),
            key=lambda item: (
                item.current_load / item.capacity,
                item.current_load,
                item.display_name.casefold(),
                str(item.expert_id),
            ),
        )
        if not candidates:
            return RoutingRecommendation(
                state="no_eligible_expert",
                recommended_expert=None,
                candidates=[],
                reason="No active expert belongs to a group eligible for this category.",
            )
        available = [candidate for candidate in candidates if candidate.available]
        if not available:
            return RoutingRecommendation(
                state="all_eligible_experts_overloaded",
                recommended_expert=None,
                candidates=candidates,
                reason="All eligible experts are at or above configured capacity.",
            )
        recommended = available[0]
        return RoutingRecommendation(
            state="recommended",
            recommended_expert=recommended,
            candidates=candidates,
            reason=(
                "Lowest active-load-to-capacity ratio among active experts in eligible groups."
            ),
        )
