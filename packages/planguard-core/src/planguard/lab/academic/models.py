"""Deterministic in-memory academic domain used by the Milestone D laboratory."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Institution:
    id: int
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class Program:
    id: int
    institution_id: int
    code: str
    title: str


@dataclass(frozen=True, slots=True)
class Course:
    id: int
    institution_id: int
    subject: str
    number: int
    title: str
    credits: int


@dataclass(frozen=True, slots=True)
class Student:
    id: int
    institution_id: int
    program_id: int
    external_id: str
    active: bool = True


@dataclass(frozen=True, slots=True)
class Enrollment:
    id: int
    institution_id: int
    student_id: int
    course_id: int
    term: str
    grade: str


@dataclass(frozen=True, slots=True)
class PlanItem:
    id: int
    institution_id: int
    student_id: int
    course_id: int
    position: int


@dataclass(slots=True)
class AcademicDataset:
    institutions: tuple[Institution, ...]
    programs: tuple[Program, ...]
    courses: tuple[Course, ...]
    students: tuple[Student, ...]
    enrollments: tuple[Enrollment, ...]
    plan_items: tuple[PlanItem, ...]
    logical_counts: dict[str, int]
    seed: int
    scale_profile: str
    tenant_skew: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def institution(self, institution_id: int) -> Institution:
        return next(item for item in self.institutions if item.id == institution_id)

    def students_for_tenant(self, institution_id: int) -> tuple[Student, ...]:
        return tuple(item for item in self.students if item.institution_id == institution_id)

    def plan_items_for_student(self, student_id: int) -> tuple[PlanItem, ...]:
        return tuple(sorted((item for item in self.plan_items if item.student_id == student_id), key=lambda item: item.position))

    def enrollments_for_student(self, student_id: int) -> tuple[Enrollment, ...]:
        return tuple(item for item in self.enrollments if item.student_id == student_id)

    def course(self, course_id: int) -> Course:
        return next(item for item in self.courses if item.id == course_id)

    def fingerprint_material(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "scale_profile": self.scale_profile,
            "tenant_skew": self.tenant_skew,
            "logical_counts": dict(sorted(self.logical_counts.items())),
            "institution_codes": [item.code for item in self.institutions],
            "student_sample": [item.external_id for item in self.students[:32]],
            "course_sample": [f"{item.subject}{item.number}" for item in self.courses[:32]],
        }
