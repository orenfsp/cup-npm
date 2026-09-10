from typing import cast
from uuid import uuid4

from app.db.models import ExpertProfile, SpecialistGroup, StaffUser
from app.db.models.enums import StaffRole
from app.db.repositories.operator import OperatorRepository, RoutingCandidateRecord
from app.modules.routing.service import RoutingService


class FakeRoutingRepository:
    def __init__(self, records: list[RoutingCandidateRecord]) -> None:
        self.records = records

    async def routing_candidates(self, category_id):
        del category_id
        return self.records


def _candidate(
    name: str,
    *,
    load: int,
    capacity: int,
    group: str = "Психологи",
    active: bool = True,
) -> RoutingCandidateRecord:
    staff_id = uuid4()
    return RoutingCandidateRecord(
        staff=StaffUser(
            id=staff_id,
            login=f"expert-{staff_id}",
            password_hash="argon2",
            role=StaffRole.EXPERT,
            is_active=active,
            display_name=name,
        ),
        profile=ExpertProfile(staff_user_id=staff_id, max_active_appeals=capacity),
        group=SpecialistGroup(id=uuid4(), slug=f"group-{staff_id}", name=group, is_active=True),
        current_load=load,
    )


async def test_routing_recommends_lowest_workload_ratio_without_assigning() -> None:
    busy = _candidate("Busy", load=4, capacity=5)
    available = _candidate("Available", load=2, capacity=10)
    service = RoutingService(cast(OperatorRepository, FakeRoutingRepository([busy, available])))

    result = await service.recommend(uuid4())

    assert result.state == "recommended"
    assert result.recommended_expert is not None
    assert result.recommended_expert.expert_id == available.staff.id
    assert result.recommended_expert.current_load == 2
    assert result.recommended_expert.capacity == 10


async def test_routing_groups_duplicate_eligible_memberships() -> None:
    first = _candidate("Expert", load=1, capacity=4, group="Психологи")
    second = RoutingCandidateRecord(
        staff=first.staff,
        profile=first.profile,
        group=SpecialistGroup(id=uuid4(), slug="lawyers", name="Юристы", is_active=True),
        current_load=1,
    )
    result = await RoutingService(
        cast(OperatorRepository, FakeRoutingRepository([first, second]))
    ).recommend(uuid4())
    assert result.candidates[0].groups == ["Психологи", "Юристы"]


async def test_routing_reports_no_eligible_and_overloaded_states() -> None:
    none = await RoutingService(cast(OperatorRepository, FakeRoutingRepository([]))).recommend(
        uuid4()
    )
    overloaded_record = _candidate("Full", load=5, capacity=5)
    overloaded = await RoutingService(
        cast(OperatorRepository, FakeRoutingRepository([overloaded_record]))
    ).recommend(uuid4())

    assert none.state == "no_eligible_expert"
    assert none.recommended_expert is None
    assert overloaded.state == "all_eligible_experts_overloaded"
    assert overloaded.recommended_expert is None
    assert overloaded.candidates[0].available is False


async def test_inactive_expert_is_ignored() -> None:
    inactive = _candidate("Inactive", load=0, capacity=5, active=False)
    result = await RoutingService(
        cast(OperatorRepository, FakeRoutingRepository([inactive]))
    ).recommend(uuid4())
    assert result.state == "no_eligible_expert"
