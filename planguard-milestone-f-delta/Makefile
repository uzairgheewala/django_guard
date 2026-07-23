.PHONY: contracts seed test api ui-install ui-build

contracts:
	python scripts/generate_contracts.py

seed:
	python scripts/seed_sample_artifacts.py --store examples/store
	python scripts/seed_milestone_b_artifacts.py --store examples/store
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_c_artifacts.py
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_d_artifacts.py
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_e_artifacts.py
	PYTHONPATH=packages/planguard-core/src python scripts/seed_milestone_f_artifacts.py

test:
	pytest

api:
	PLANGUARD_STORE=examples/store python services/workbench_api/manage.py runserver

ui-install:
	cd apps/workbench-ui && npm install

ui-build:
	cd apps/workbench-ui && npm run build
