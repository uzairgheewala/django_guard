from .adapter import AcademicScenarioAdapter
from .bootstrap import AcademicCatalog, build_academic_catalog
from .catalog import builtin_bindings, builtin_mutations, builtin_templates
from .generator import AcademicDatasetGenerator, SCALE_PROFILES, ScaleProfile
from .models import AcademicDataset, Course, Enrollment, Institution, PlanItem, Program, Student

__all__ = [
    "AcademicCatalog",
    "AcademicDataset",
    "AcademicDatasetGenerator",
    "AcademicScenarioAdapter",
    "Course",
    "Enrollment",
    "Institution",
    "PlanItem",
    "Program",
    "SCALE_PROFILES",
    "ScaleProfile",
    "Student",
    "build_academic_catalog",
    "builtin_bindings",
    "builtin_mutations",
    "builtin_templates",
]
