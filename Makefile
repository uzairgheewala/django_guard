.PHONY: contracts seed test api ui-install ui-build

contracts:
	python scripts/generate_contracts.py

seed:
	python scripts/seed_sample_artifacts.py --store examples/store
	python scripts/seed_milestone_b_artifacts.py --store examples/store

test:
	pytest

api:
	PLANGUARD_STORE=examples/store python services/workbench_api/manage.py runserver

ui-install:
	cd apps/workbench-ui && npm install

ui-build:
	cd apps/workbench-ui && npm run build
