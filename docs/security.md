# Security and redaction

PlanGuard artifacts may contain SQL, parameter values, source paths, environment details, tenant identifiers, or application metadata. Safe defaults reduce exposure, but every exported bundle should be audited.

## Controls

- raw SQL is redacted by default;
- parameter values are represented by shape and optional HMAC identity by default;
- preserved values and SQL produce security findings;
- sanitization creates a new schema-compatible artifact and receipt;
- original artifacts remain immutable;
- invalid imports are quarantined;
- artifact and store quotas bound local resource use;
- live plan execution and laboratory execution are separately gated.

## Limitations

Pattern scanning can miss domain-specific personal or confidential data. Sanitized artifacts should be re-audited before external sharing. Third-party plugins may access the data passed to them and must be reviewed independently.
