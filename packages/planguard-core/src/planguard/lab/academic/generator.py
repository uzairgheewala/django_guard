"""Distribution-aware deterministic academic dataset generator."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from planguard.artifacts.models import (
    DatasetManifestArtifact,
    DatasetManifestPayload,
    DistributionSpec,
    ProducerIdentity,
    Provenance,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch
from planguard.lab.academic.models import AcademicDataset, Course, Enrollment, Institution, PlanItem, Program, Student


@dataclass(frozen=True, slots=True)
class ScaleProfile:
    institutions: int
    materialized_students: int
    logical_students: int
    courses_per_tenant: int
    enrollments_per_student: int
    plan_items_per_student: int


SCALE_PROFILES: dict[str, ScaleProfile] = {
    "tiny": ScaleProfile(2, 40, 40, 36, 8, 5),
    "small": ScaleProfile(3, 180, 5_000, 80, 12, 7),
    "medium": ScaleProfile(10, 500, 100_000, 140, 16, 9),
    "large": ScaleProfile(20, 1_000, 500_000, 220, 20, 12),
}


class AcademicDatasetGenerator:
    generator_key = "academic.synthetic.v1"

    def __init__(self, producer: ProducerIdentity) -> None:
        self.producer = producer

    def generate(
        self,
        *,
        seed: int,
        scale_profile: str = "tiny",
        tenant_skew: str = "uniform",
        relation_fanout: int | None = None,
        tenant_count: int | None = None,
    ) -> tuple[AcademicDataset, DatasetManifestArtifact]:
        if scale_profile not in SCALE_PROFILES:
            raise ValueError(f"Unknown academic scale profile: {scale_profile}")
        profile = SCALE_PROFILES[scale_profile]
        rng = random.Random(seed)
        institutions_count = tenant_count or profile.institutions
        institutions = tuple(Institution(id=index + 1, code=f"INST{index + 1:02d}", name=f"Institution {index + 1}") for index in range(institutions_count))
        programs = tuple(Program(id=index + 1, institution_id=institution.id, code="DS", title="Data Science") for index, institution in enumerate(institutions))

        courses: list[Course] = []
        for institution in institutions:
            for index in range(profile.courses_per_tenant):
                courses.append(Course(id=institution.id * 100_000 + index + 1, institution_id=institution.id, subject="CSE" if index % 2 else "DSC", number=10 + index, title=f"Course {index + 1}", credits=4))

        weights = self._tenant_weights(institutions_count, tenant_skew)
        materialized_total = max(profile.materialized_students, institutions_count)
        tenant_student_counts = self._allocate(materialized_total, weights)
        students: list[Student] = []
        for institution, count in zip(institutions, tenant_student_counts):
            program = next(item for item in programs if item.institution_id == institution.id)
            for _ in range(count):
                index = len(students) + 1
                students.append(Student(id=index, institution_id=institution.id, program_id=program.id, external_id=f"{institution.code}-S{index:06d}"))

        enrollments: list[Enrollment] = []
        plan_items: list[PlanItem] = []
        by_tenant_courses = {institution.id: [item for item in courses if item.institution_id == institution.id] for institution in institutions}
        plan_count = relation_fanout if relation_fanout is not None else profile.plan_items_per_student
        for student in students:
            tenant_courses = by_tenant_courses[student.institution_id]
            selected = rng.sample(tenant_courses, k=min(profile.enrollments_per_student, len(tenant_courses)))
            for course in selected:
                enrollments.append(Enrollment(id=len(enrollments) + 1, institution_id=student.institution_id, student_id=student.id, course_id=course.id, term=f"20{24 + len(enrollments) % 4}-FA", grade=rng.choice(("A", "A-", "B+", "B"))))
            planned = rng.sample(tenant_courses, k=min(plan_count, len(tenant_courses)))
            for position, course in enumerate(planned, start=1):
                plan_items.append(PlanItem(id=len(plan_items) + 1, institution_id=student.institution_id, student_id=student.id, course_id=course.id, position=position))

        logical_counts = {
            "institution": institutions_count,
            "program": institutions_count,
            "course": institutions_count * profile.courses_per_tenant,
            "student": profile.logical_students,
            "enrollment": profile.logical_students * profile.enrollments_per_student,
            "plan_item": profile.logical_students * plan_count,
        }
        dataset = AcademicDataset(
            institutions=institutions,
            programs=programs,
            courses=tuple(courses),
            students=tuple(students),
            enrollments=tuple(enrollments),
            plan_items=tuple(plan_items),
            logical_counts=logical_counts,
            seed=seed,
            scale_profile=scale_profile,
            tenant_skew=tenant_skew,
            metadata={"materialized_students": len(students), "tenant_student_counts": tenant_student_counts},
        )
        material = dataset.fingerprint_material()
        fingerprint = "sha256:" + hashlib.sha256(canonical_json_bytes(material)).hexdigest()
        payload = DatasetManifestPayload(
            dataset_key=f"academic:{scale_profile}:{tenant_skew}",
            dataset_version="academic-dataset.v1",
            generator_key=self.generator_key,
            seed=seed,
            scale_profile=scale_profile,
            entity_counts=logical_counts,
            distributions=(
                DistributionSpec(distribution_key="tenant-allocation", kind=tenant_skew, parameters={"weights": weights}),
                DistributionSpec(distribution_key="course-popularity", kind="bounded-uniform", parameters={"courses_per_tenant": profile.courses_per_tenant}),
                DistributionSpec(distribution_key="relation-fanout", kind="fixed", parameters={"plan_items_per_student": plan_count}),
            ),
            constraints=("all domain rows carry institution_id", "cross-tenant foreign keys are forbidden", "materialized rows are a deterministic representative projection"),
            dataset_fingerprint=fingerprint,
            tenant_count=institutions_count,
            metadata={"materialized_counts": {"student": len(students), "enrollment": len(enrollments), "plan_item": len(plan_items)}, "generator_material": material},
        )
        artifact = DatasetManifestArtifact(
            created_at=semantic_epoch(),
            artifact_id=content_derived_id("dset", canonical_json_bytes({"payload": payload, "producer": self.producer.model_dump(mode="python")}), length=32),
            producer=self.producer,
            provenance=Provenance(derivation_key=self.generator_key),
            payload=payload,
        ).seal()
        return dataset, artifact

    @staticmethod
    def _tenant_weights(count: int, skew: str) -> list[float]:
        if skew == "uniform":
            return [1.0] * count
        if skew == "dominant":
            return [8.0] + [1.0] * (count - 1)
        if skew == "zipf":
            return [1.0 / (index + 1) for index in range(count)]
        raise ValueError(f"Unknown tenant skew: {skew}")

    @staticmethod
    def _allocate(total: int, weights: list[float]) -> list[int]:
        denominator = sum(weights)
        raw = [max(1, int(total * weight / denominator)) for weight in weights]
        while sum(raw) < total:
            raw[raw.index(min(raw))] += 1
        while sum(raw) > total:
            index = raw.index(max(raw))
            if raw[index] > 1:
                raw[index] -= 1
            else:
                break
        return raw
