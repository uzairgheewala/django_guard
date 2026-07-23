# Security policy

Do not include real credentials, production database dumps, or unredacted personal data in public issues or demonstration artifacts.

Before sharing a bundle:

```bash
planguard security-audit --all --store PATH
planguard trust-verify --all --store PATH
```

Use `sanitize-artifact` for shareable derivatives. Preserve the original artifact privately for provenance. Vulnerability reports should include the affected version, artifact kind, reproduction steps using synthetic data, and whether live plan or laboratory execution was enabled.
