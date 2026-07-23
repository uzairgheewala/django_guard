# Contributing

Changes should preserve the artifact-first boundary.

1. Add or update the canonical Pydantic contract.
2. Regenerate JSON Schema and TypeScript contracts.
3. Add contract, property, integration, and golden tests as appropriate.
4. Keep unsupported and unknown states explicit.
5. Include a documented case when changing detector, plan, benchmark, or security behavior.
6. Do not automatically rewrite ORM/SQL code or create indexes.

Run:

```bash
make contracts
pytest
```
