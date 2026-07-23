"""Artifact security scanning, sanitization, and trust assessment.

The scanner is intentionally conservative. It identifies evidence of sensitive
capture and integrity problems; it does not claim that a clean report proves an
artifact contains no personal or secret information.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from planguard.artifacts.codec import default_codec
from planguard.artifacts.models import (
    AnyArtifact,
    ArtifactDocument,
    ArtifactReference,
    ArtifactSanitizationArtifact,
    ArtifactSanitizationPayload,
    ArtifactTrustReportArtifact,
    ArtifactTrustReportPayload,
    ParameterCaptureMode,
    ProducerIdentity,
    Provenance,
    RedactionRule,
    RawSqlMode,
    SecurityAuditArtifact,
    SecurityAuditPayload,
    SecurityFinding,
    SecurityRiskLevel,
    TrustState,
    WorkflowStatus,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import new_artifact_id
from planguard.store.filesystem import FilesystemArtifactStore


DEFAULT_REDACTION_RULES: tuple[RedactionRule, ...] = (
    RedactionRule(rule_key="credential-field.v1", kind="field_name", pattern=r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie|session)", risk_level=SecurityRiskLevel.CRITICAL),
    RedactionRule(rule_key="email-address.v1", kind="value_pattern", pattern=r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", risk_level=SecurityRiskLevel.HIGH),
    RedactionRule(rule_key="bearer-token.v1", kind="value_pattern", pattern=r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", risk_level=SecurityRiskLevel.CRITICAL),
    RedactionRule(rule_key="private-key.v1", kind="value_pattern", pattern=r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", risk_level=SecurityRiskLevel.CRITICAL),
    RedactionRule(rule_key="payment-card.v1", kind="value_pattern", pattern=r"\b(?:\d[ -]*?){13,19}\b", risk_level=SecurityRiskLevel.HIGH),
    RedactionRule(rule_key="absolute-path.v1", kind="absolute_path", pattern=r"(?:^|[\s\"'])(?:/[A-Za-z0-9_.-]+){2,}|[A-Za-z]:\\(?:[^\\\s]+\\)+[^\\\s]+", risk_level=SecurityRiskLevel.MEDIUM),
    RedactionRule(rule_key="preserved-parameter.v1", kind="parameter_value", risk_level=SecurityRiskLevel.HIGH),
    RedactionRule(rule_key="preserved-sql.v1", kind="sql_literal", risk_level=SecurityRiskLevel.MEDIUM),
)


@dataclass(frozen=True, slots=True)
class _Match:
    rule: RedactionRule
    path: str
    evidence: str


def _walk(value: Any, path: str = "$"):
    yield path, None, value
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), child
            yield from _walk(child, child_path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            yield from _walk(child, f"{path}[{index}]")


def _matches(document: Mapping[str, Any], rules: Sequence[RedactionRule]) -> list[_Match]:
    matches: list[_Match] = []
    for path, key, value in _walk(document):
        for rule in rules:
            if not rule.enabled:
                continue
            if rule.kind == "field_name" and key and rule.pattern and re.search(rule.pattern, key):
                matches.append(_Match(rule, path, f"Sensitive field name {key!r}"))
            elif rule.kind in {"value_pattern", "absolute_path"} and isinstance(value, str) and rule.pattern and re.search(rule.pattern, value):
                excerpt = value[:120].replace("\n", " ")
                matches.append(_Match(rule, path, f"Value matched {rule.rule_key}: {excerpt}"))
            elif rule.kind == "parameter_value" and key == "preserved_value" and value is not None:
                matches.append(_Match(rule, path, "Captured parameter value is preserved."))
            elif rule.kind == "sql_literal" and key == "raw_sql_mode" and value == str(RawSqlMode.PRESERVE):
                matches.append(_Match(rule, path, "Raw SQL capture mode preserves statement literals."))
    unique: dict[tuple[str, str], _Match] = {}
    for match in matches:
        unique[(match.rule.rule_key, match.path)] = match
    return list(unique.values())


def _status_counts(findings: Sequence[SecurityFinding]) -> dict[str, int]:
    counter = Counter(str(item.risk_level) for item in findings)
    return dict(sorted(counter.items()))


def audit_artifacts(
    artifacts: Iterable[AnyArtifact],
    *,
    producer: ProducerIdentity,
    rules: Sequence[RedactionRule] = DEFAULT_REDACTION_RULES,
    integrity_results: Mapping[str, bool] | None = None,
) -> SecurityAuditArtifact:
    materialized = tuple(artifacts)
    findings: list[SecurityFinding] = []
    scanned_bytes = 0
    verified = failed = 0
    for artifact in materialized:
        document = artifact.model_dump(mode="json", exclude_none=False)
        scanned_bytes += len(canonical_json_bytes(document))
        integrity = artifact.verify_integrity() if integrity_results is None else integrity_results.get(artifact.artifact_id, False)
        if integrity:
            verified += 1
        else:
            failed += 1
            findings.append(SecurityFinding(
                finding_key=f"integrity:{artifact.artifact_id}",
                risk_level=SecurityRiskLevel.CRITICAL,
                category="artifact_integrity",
                artifact_ref=artifact.reference(),
                evidence="The artifact content hash did not verify.",
                recommendation="Quarantine the artifact and recover it from a trusted source.",
                automatically_redactable=False,
            ))
        for match in _matches(document, rules):
            findings.append(SecurityFinding(
                finding_key=f"{match.rule.rule_key}:{artifact.artifact_id}:{match.path}",
                risk_level=match.rule.risk_level,
                category=match.rule.kind,
                artifact_ref=artifact.reference(),
                json_path=match.path,
                evidence=match.evidence,
                recommendation="Sanitize this field before sharing or exporting the artifact.",
                automatically_redactable=True,
            ))
    levels = {str(item.risk_level) for item in findings}
    if failed or "critical" in levels:
        trust = TrustState.UNTRUSTED
    elif "high" in levels or "medium" in levels:
        trust = TrustState.PARTIAL
    else:
        trust = TrustState.TRUSTED
    return SecurityAuditArtifact(
        producer=producer,
        provenance=Provenance(input_refs=tuple(item.reference() for item in materialized), derivation_key="security-audit.v1"),
        payload=SecurityAuditPayload(
            subject_refs=tuple(item.reference() for item in materialized),
            scanned_artifact_count=len(materialized),
            trust_state=trust,
            findings=tuple(findings),
            status_counts=_status_counts(findings),
            integrity_verified=verified,
            integrity_failed=failed,
            scanned_bytes=scanned_bytes,
            rules=tuple(rules),
            limitations=("Pattern scanning cannot prove the absence of sensitive or identifying information.",),
        ),
    ).seal()


def _sanitize(value: Any, rules: Sequence[RedactionRule], path: str, redacted: list[str], *, key: str | None = None) -> Any:
    field_matches = [rule for rule in rules if rule.enabled and rule.kind == "field_name" and key and rule.pattern and re.search(rule.pattern, key)]
    if field_matches and not isinstance(value, (Mapping, list, tuple)):
        redacted.append(path)
        return field_matches[0].replacement
    if key == "preserved_value" and value is not None:
        rule = next((item for item in rules if item.enabled and item.kind == "parameter_value"), None)
        if rule:
            redacted.append(path)
            return None
    if key == "raw_sql_mode" and value == str(RawSqlMode.PRESERVE):
        redacted.append(path)
        return str(RawSqlMode.REDACT)
    if isinstance(value, Mapping):
        return {name: _sanitize(child, rules, f"{path}.{name}", redacted, key=str(name)) for name, child in value.items()}
    if isinstance(value, list):
        return [_sanitize(child, rules, f"{path}[{index}]", redacted) for index, child in enumerate(value)]
    if isinstance(value, tuple):
        return tuple(_sanitize(child, rules, f"{path}[{index}]", redacted) for index, child in enumerate(value))
    if isinstance(value, str):
        rendered = value
        for rule in rules:
            if not rule.enabled or rule.kind not in {"value_pattern", "absolute_path"} or not rule.pattern:
                continue
            replaced = re.sub(rule.pattern, rule.replacement, rendered)
            if replaced != rendered:
                redacted.append(path)
                rendered = replaced
        return rendered
    return value


def sanitize_artifact(
    artifact: AnyArtifact,
    *,
    producer: ProducerIdentity,
    rules: Sequence[RedactionRule] = DEFAULT_REDACTION_RULES,
) -> tuple[AnyArtifact, ArtifactSanitizationArtifact]:
    raw = artifact.model_dump(mode="python", exclude={"content_hash"}, exclude_none=False)
    redacted_paths: list[str] = []
    raw["payload"] = _sanitize(raw["payload"], rules, "$.payload", redacted_paths)
    raw["extensions"] = _sanitize(raw["extensions"], rules, "$.extensions", redacted_paths)
    raw["artifact_id"] = new_artifact_id("san")
    raw["producer"] = producer.model_dump(mode="python")
    provenance = artifact.provenance.model_dump(mode="python")
    provenance["input_refs"] = tuple((*artifact.provenance.input_refs, artifact.reference()))
    provenance["derivation_key"] = "artifact-sanitization.v1"
    raw["provenance"] = provenance
    model = type(artifact)
    sanitized = model.model_validate(raw).seal()
    before = len(default_codec.encode(artifact))
    after = len(default_codec.encode(sanitized))
    receipt = ArtifactSanitizationArtifact(
        producer=producer,
        provenance=Provenance(input_refs=(artifact.reference(), sanitized.reference()), derivation_key="artifact-sanitization-receipt.v1"),
        payload=ArtifactSanitizationPayload(
            source_ref=artifact.reference(),
            sanitized_ref=sanitized.reference(),
            status=WorkflowStatus.COMPLETED,
            applied_rule_keys=tuple(sorted({rule.rule_key for rule in rules if rule.enabled})),
            redacted_paths=tuple(sorted(set(redacted_paths))),
            before_bytes=before,
            after_bytes=after,
            warnings=("The sanitized artifact must be re-audited before external sharing.",),
        ),
    ).seal()
    return sanitized, receipt


def verify_artifact_trust(
    store: FilesystemArtifactStore,
    artifact_ids: Iterable[str],
    *,
    producer: ProducerIdentity,
) -> ArtifactTrustReportArtifact:
    verified: list[ArtifactReference] = []
    failed: list[ArtifactReference] = []
    missing: list[ArtifactReference] = []
    subjects: list[ArtifactReference] = []
    seen_missing: set[str] = set()
    for artifact_id in artifact_ids:
        try:
            artifact = store.load(artifact_id)
        except Exception:
            missing.append(ArtifactReference(artifact_id=artifact_id, artifact_kind="unknown"))
            seen_missing.add(artifact_id)
            continue
        subjects.append(artifact.reference())
        (verified if store.verify(artifact_id) else failed).append(artifact.reference())
        for reference in artifact.provenance.input_refs:
            try:
                referenced = store.load(reference.artifact_id)
            except Exception:
                if reference.artifact_id not in seen_missing:
                    missing.append(reference)
                    seen_missing.add(reference.artifact_id)
                continue
            if reference.content_hash and referenced.content_hash != reference.content_hash:
                failed.append(reference)
    trust = TrustState.TRUSTED if subjects and not failed and not missing else (TrustState.UNTRUSTED if failed else TrustState.PARTIAL)
    return ArtifactTrustReportArtifact(
        producer=producer,
        provenance=Provenance(input_refs=tuple(subjects), derivation_key="artifact-trust.v1"),
        payload=ArtifactTrustReportPayload(
            subject_refs=tuple(subjects),
            trust_state=trust,
            verified_refs=tuple(verified),
            failed_refs=tuple(failed),
            missing_refs=tuple(missing),
            checks={"content_hash": True, "pointer_identity": True},
            explanation=(
                f"Verified {len(verified)} artifacts; {len(failed)} failed and {len(missing)} were missing.",
            ),
        ),
    ).seal()
