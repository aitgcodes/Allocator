from dataclasses import dataclass, field
from typing import List, Dict, Optional
from collections import defaultdict


@dataclass
class Student:
    id: str
    cpi: float
    class_tier: str  # 'A', 'B', or 'C'
    preferences: List[str]  # ordered list of advisor_ids


@dataclass
class Advisor:
    id: str
    max_load: int
    current_load: int = 0


@dataclass
class AllocationResult:
    assignments: Dict[str, str]  # student_id -> advisor_id
    unassigned: List[str]  # remaining student_ids
    advisor_loads: Dict[str, int]


def sort_students_by_cpi(students: List[Student]) -> List[Student]:
    return sorted(students, key=lambda s: s.cpi, reverse=True)


def first_choice_pass(
    students: List[Student], advisors: Dict[str, Advisor]
) -> AllocationResult:
    """Round 1: global first preference, CPI-ordered."""
    assignments = {}
    # Work on a copy of loads
    advisor_loads = {aid: adv.current_load for aid, adv in advisors.items()}

    for s in sort_students_by_cpi(students):
        if not s.preferences:
            continue
        first_choice = s.preferences[0]
        adv = advisors[first_choice]
        if advisor_loads[first_choice] < adv.max_load:
            assignments[s.id] = first_choice
            advisor_loads[first_choice] += 1

    unassigned = [s.id for s in students if s.id not in assignments]
    return AllocationResult(assignments, unassigned, advisor_loads)


def least_loaded_choice(
    student: Student,
    advisor_ids: List[str],
    advisors: Dict[str, Advisor],
    advisor_loads: Dict[str, int],
) -> Optional[str]:
    """Pick least-loaded advisor among advisor_ids with remaining capacity,
    tie-break by earliest in student's preference list."""
    eligible = []
    for aid in advisor_ids:
        adv = advisors[aid]
        if advisor_loads[aid] < adv.max_load:
            eligible.append(aid)
    if not eligible:
        return None

    # Find minimum load among eligible
    min_load = min(advisor_loads[aid] for aid in eligible)
    candidates = [aid for aid in eligible if advisor_loads[aid] == min_load]

    # tie-break by earliest position in student's preference list
    pref_index = {aid: i for i, aid in enumerate(student.preferences)}
    candidates.sort(key=lambda aid: pref_index.get(aid, len(student.preferences)))
    return candidates[0]


def class_wise_allocation(
    students: List[Student], advisors: Dict[str, Advisor], N_A: int, N_B: int
) -> AllocationResult:
    """Implements 3.3.1 and 3.3.2 assuming:
    - A, B: class-wise caps N_A, N_B
    - C: global cap (full list)
    """
    # Start from loads after first-choice pass
    fc_result = first_choice_pass(students, advisors)
    assignments = dict(fc_result.assignments)
    advisor_loads = dict(fc_result.advisor_loads)

    # Helper: maps id -> Student
    student_by_id = {s.id: s for s in students}

    def unassigned_of_class(tier: str, pool: List[str]) -> List[str]:
        return [
            sid
            for sid in pool
            if student_by_id[sid].class_tier == tier and sid not in assignments
        ]

    # Full list of unassigned after first choice
    remaining = fc_result.unassigned

    # Class A main round (within 1 -> N_A)
    for sid in sort_students_by_cpi(
        [student_by_id[x] for x in remaining if student_by_id[x].class_tier == "A"]
    ):
        s = student_by_id[sid]
        top_cap = s.preferences[:N_A]
        choice = least_loaded_choice(s, top_cap, advisors, advisor_loads)
        if choice is not None:
            assignments[s.id] = choice
            advisor_loads[choice] += 1

    # Build pool for Class B: original B + leftover A
    remaining_after_A = [sid for sid in remaining if sid not in assignments]
    pool_B = [
        sid for sid in remaining_after_A if student_by_id[sid].class_tier in ["A", "B"]
    ]

    # Class B main round (within 1 -> N_B)
    for sid in sort_students_by_cpi([student_by_id[x] for x in pool_B]):
        s = student_by_id[sid]
        top_cap = s.preferences[:N_B]
        choice = least_loaded_choice(s, top_cap, advisors, advisor_loads)
        if choice is not None:
            assignments[s.id] = choice
            advisor_loads[choice] += 1

    # Class C (global cap: all advisors with capacity)
    # Remaining = everyone not assigned yet
    remaining_final = [sid for sid in remaining_after_A if sid not in assignments] + [
        sid
        for sid in remaining
        if student_by_id[sid].class_tier == "C" and sid not in assignments
    ]

    # Deduplicate remaining_final
    remaining_final = list(dict.fromkeys(remaining_final))

    all_advisors = list(advisors.keys())

    for sid in sort_students_by_cpi([student_by_id[x] for x in remaining_final]):
        s = student_by_id[sid]
        choice = least_loaded_choice(s, all_advisors, advisors, advisor_loads)
        if choice is not None:
            assignments[s.id] = choice
            advisor_loads[choice] += 1
        # else: stays unassigned (e.g., all at max_load)

    unassigned = [s.id for s in students if s.id not in assignments]
    return AllocationResult(assignments, unassigned, advisor_loads)
