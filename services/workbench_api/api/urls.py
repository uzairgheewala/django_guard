from django.urls import path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("capabilities", views.capabilities, name="capabilities"),
    path("artifacts", views.artifacts, name="artifacts"),
    path("artifacts/<str:artifact_id>", views.artifact_detail, name="artifact-detail"),
    path(
        "artifacts/<str:artifact_id>/integrity",
        views.artifact_integrity,
        name="artifact-integrity",
    ),
    path("import", views.import_artifact, name="import-artifact"),
    path("runs", views.runs, name="runs"),
    path("runs/<str:run_id>", views.run_detail, name="run-detail"),
    path("runs/<str:run_id>/families", views.run_families, name="run-families"),
    path("runs/<str:run_id>/findings", views.run_findings, name="run-findings"),
    path(
        "runs/<str:run_id>/policy-evaluations",
        views.evaluate_run_policy,
        name="run-policy-evaluation",
    ),
]
