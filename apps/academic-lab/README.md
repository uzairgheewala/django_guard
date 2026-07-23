# Academic Laboratory

This optional Django application supplies a realistic shared-schema, multi-tenant academic domain for PlanGuard scenario bindings. The deterministic in-memory adapter under `planguard.lab.academic` is the default test runner, while these Django models allow the same generic templates to be rebound to a real ORM/PostgreSQL environment.

The core scenario engine does not import these models. Install Django, add `academic_lab` to `INSTALLED_APPS`, migrate, and register a Django-backed adapter to replace the deterministic adapter.
