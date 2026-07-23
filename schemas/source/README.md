# Source schemas

The source of truth is the Pydantic model set in:

`packages/planguard-core/src/planguard/artifacts/models.py`

Do not hand-edit files in `schemas/generated/`. Regenerate them with:

```bash
python scripts/generate_contracts.py
```
