"""Optional ORM binding surface for the academic scenario catalog."""

from django.db import models


class Institution(models.Model):
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)


class TenantScopedModel(models.Model):
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class Program(TenantScopedModel):
    code = models.CharField(max_length=32)
    title = models.CharField(max_length=255)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("institution", "code"), name="academic_program_tenant_code_uq")]


class Course(TenantScopedModel):
    subject = models.CharField(max_length=16)
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    credits = models.PositiveSmallIntegerField(default=4)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("institution", "subject", "number"), name="academic_course_tenant_catalog_uq")]
        indexes = [models.Index(fields=("institution", "active", "subject", "number"), name="academic_course_search_idx")]


class Student(TenantScopedModel):
    external_id = models.CharField(max_length=64)
    program = models.ForeignKey(Program, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("institution", "external_id"), name="academic_student_tenant_external_uq")]
        indexes = [models.Index(fields=("institution", "active", "id"), name="academic_student_active_idx")]


class Enrollment(TenantScopedModel):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    term = models.CharField(max_length=16)
    grade = models.CharField(max_length=8, blank=True)
    source_key = models.CharField(max_length=128, blank=True)

    class Meta:
        indexes = [models.Index(fields=("institution", "student", "term"), name="academic_enrollment_lookup_idx")]


class StudentPlan(TenantScopedModel):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="plan")
    updated_at = models.DateTimeField(auto_now=True)


class PlanItem(TenantScopedModel):
    plan = models.ForeignKey(StudentPlan, on_delete=models.CASCADE, related_name="items")
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    position = models.PositiveIntegerField()

    class Meta:
        ordering = ("position",)
        indexes = [models.Index(fields=("institution", "plan", "position"), name="academic_plan_item_order_idx")]


class AuditSummary(TenantScopedModel):
    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    completed_credits = models.PositiveIntegerField(default=0)


class Appointment(TenantScopedModel):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    starts_at = models.DateTimeField()
    status = models.CharField(max_length=32)
