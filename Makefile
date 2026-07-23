.PHONY: contracts seed test api ui-install ui-build package-check release-check checksums

contracts:
	python scripts/generate_contracts.py

seed:
	python scripts/seed_sample_artifacts.py --store examples/store
	python scripts/seed_milestone_b_artifacts.py --store examples/store
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_c_artifacts.py
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_d_artifacts.py
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_e_artifacts.py
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_f_artifacts.py
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_g_artifacts.py

test:
	pytest

api:
	PLANGUARD_STORE=examples/store python services/workbench_api/manage.py runserver

ui-install:
	cd apps/workbench-ui && npm install

ui-build:
	cd apps/workbench-ui && npm run build

package-check:
	python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist

release-check:
	python scripts/generate_contracts.py --check
	pytest
	PYTHONPATH=packages/planguard-core/src python -m planguard.cli release-build --store examples/store --status candidate

checksums:
	python scripts/generate_repository_checksums.py
