"""Conservative SQL normalization and feature extraction.

Milestone B intentionally avoids pretending to prove semantic SQL equivalence.
The normalizer provides a deterministic lexical/structural approximation and
marks its parse quality explicitly. A future SQL-AST adapter can replace or
augment this implementation without changing artifact contracts.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable

from planguard.artifacts.models import ParseQuality, QueryFeatures
from planguard.canonical import canonical_json_bytes

_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COMMENT = re.compile(r"--[^\n\r]*")
_STRING_LITERAL = re.compile(r"'(?:''|[^'])*'")
_DOLLAR_STRING = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)?\$.*?\$\1\$", re.DOTALL)
_NUMBER_LITERAL = re.compile(r"(?<![A-Za-z0-9_])(?:\d+\.\d+|\d+)(?![A-Za-z0-9_])")
_PLACEHOLDER = re.compile(r"%\([^)]+\)s|%s|\?|:\d+|\$\d+")
_WHITESPACE = re.compile(r"\s+")
_IDENTIFIER = r'(?:"(?:""|[^"])+"|[A-Za-z_][A-Za-z0-9_$]*)(?:\.(?:"(?:""|[^"])+"|[A-Za-z_][A-Za-z0-9_$]*))*'
_RELATION = re.compile(rf"\b(?:from|join|update|into)\s+({_IDENTIFIER})", re.IGNORECASE)
_DELETE_RELATION = re.compile(rf"\bdelete\s+from\s+({_IDENTIFIER})", re.IGNORECASE)
_PREDICATE_COLUMN = re.compile(
    rf"({_IDENTIFIER})\s*(?:=|<>|!=|<=|>=|<|>|\bin\b|\blike\b|\bilike\b|\bis\b)",
    re.IGNORECASE,
)
_PROJECTION = re.compile(r"^\s*select\s+(.*?)\s+from\s", re.IGNORECASE | re.DOTALL)
_AGGREGATE = re.compile(r"\b(?:count|sum|avg|min|max|string_agg|array_agg|json_agg)\s*\(", re.IGNORECASE)
_SUBQUERY = re.compile(r"\(\s*select\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class NormalizedSql:
    canonical_sql: str
    lexical_fingerprint: str
    structural_shape_fingerprint: str
    statement_kind: str
    features: QueryFeatures
    parse_quality: ParseQuality
    diagnostics: tuple[str, ...]


def _digest(prefix: str, value: str | bytes) -> str:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return f"{prefix}_{hashlib.sha256(raw).hexdigest()}"


def redact_sql(sql: str) -> str:
    """Redact literals while preserving enough structure for inspection."""

    text = _DOLLAR_STRING.sub(":string", sql)
    text = _STRING_LITERAL.sub(":string", text)
    text = _NUMBER_LITERAL.sub(":number", text)
    return text


def _strip_comments(sql: str) -> str:
    return _LINE_COMMENT.sub(" ", _BLOCK_COMMENT.sub(" ", sql))


def _canonicalize(sql: str) -> str:
    text = _strip_comments(sql).strip().rstrip(";")
    text = _DOLLAR_STRING.sub(":string", text)
    text = _STRING_LITERAL.sub(":string", text)
    text = _NUMBER_LITERAL.sub(":number", text)
    text = _PLACEHOLDER.sub(":parameter", text)
    text = _WHITESPACE.sub(" ", text)
    text = re.sub(r"\s*(<=|>=|<>|!=|=|<|>)\s*", r" \1 ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = _WHITESPACE.sub(" ", text)
    return text.strip().lower()


def _statement_kind(canonical_sql: str) -> str:
    if not canonical_sql:
        return "unknown"
    first = canonical_sql.split(" ", 1)[0]
    if first == "with":
        match = re.search(r"\b(select|insert|update|delete)\b", canonical_sql, re.IGNORECASE)
        return match.group(1).lower() if match else "with"
    return first if first in {"select", "insert", "update", "delete", "merge", "call"} else "unknown"


def _clean_identifier(value: str) -> str:
    return value.replace('"', "").lower()


def _projection_columns(sql: str) -> tuple[str, ...]:
    match = _PROJECTION.search(sql)
    if not match:
        return ()
    body = match.group(1)
    if "*" in body:
        return ("*",)
    columns: list[str] = []
    depth = 0
    current: list[str] = []
    for char in body:
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        if char == "," and depth == 0:
            token = "".join(current).strip()
            if token:
                columns.append(token.lower())
            current = []
        else:
            current.append(char)
    token = "".join(current).strip()
    if token:
        columns.append(token.lower())
    return tuple(columns[:64])


def normalize_sql(sql: str, *, dialect: str = "postgresql") -> NormalizedSql:
    diagnostics: list[str] = []
    if not isinstance(sql, str) or not sql.strip():
        canonical = ""
        quality = ParseQuality.FAILED
        diagnostics.append("SQL was empty or not a string")
    else:
        canonical = _canonicalize(sql)
        quality = ParseQuality.PARTIAL

    statement_kind = _statement_kind(canonical)
    if statement_kind == "unknown":
        quality = ParseQuality.FALLBACK if canonical else ParseQuality.FAILED
        diagnostics.append("Statement kind was not recognized by the conservative parser")

    relations = {_clean_identifier(match) for match in _RELATION.findall(canonical)}
    relations.update(_clean_identifier(match) for match in _DELETE_RELATION.findall(canonical))
    predicates = {_clean_identifier(match) for match in _PREDICATE_COLUMN.findall(canonical)}
    features = QueryFeatures(
        statement_kind=statement_kind,
        relations=tuple(sorted(relations)),
        projected_columns=_projection_columns(canonical),
        predicate_columns=tuple(sorted(predicates)),
        join_count=len(re.findall(r"\bjoin\b", canonical, re.IGNORECASE)),
        aggregate_count=len(_AGGREGATE.findall(canonical)),
        has_group_by=bool(re.search(r"\bgroup\s+by\b", canonical, re.IGNORECASE)),
        has_order_by=bool(re.search(r"\border\s+by\b", canonical, re.IGNORECASE)),
        has_limit=bool(re.search(r"\blimit\b", canonical, re.IGNORECASE)),
        has_offset=bool(re.search(r"\boffset\b", canonical, re.IGNORECASE)),
        has_cte=canonical.startswith("with "),
        has_subquery=bool(_SUBQUERY.search(canonical)),
        has_locking_clause=bool(
            re.search(r"\bfor\s+(?:update|share|no\s+key\s+update|key\s+share)\b", canonical)
        ),
    )

    structural_material = {
        "dialect": dialect,
        "canonical_sql": canonical,
        "statement_kind": statement_kind,
    }
    return NormalizedSql(
        canonical_sql=canonical,
        lexical_fingerprint=_digest("qlx", canonical),
        structural_shape_fingerprint=_digest(
            "qsh", canonical_json_bytes(structural_material)
        ),
        statement_kind=statement_kind,
        features=features,
        parse_quality=quality,
        diagnostics=tuple(diagnostics),
    )


def parameter_regime(parameters: Iterable[Any]) -> str:
    descriptors = list(parameters)
    if not descriptors:
        return "no-parameters"
    if len(descriptors) == 1:
        item = descriptors[0]
        container = getattr(item, "container", None)
        length = getattr(item, "length", None)
        type_name = getattr(item, "type_name", "unknown")
        if container in {"list", "tuple", "set", "mapping"}:
            if length == 0:
                size = "empty"
            elif length is not None and length <= 10:
                size = "small"
            elif length is not None and length <= 100:
                size = "medium"
            else:
                size = "large"
            return f"{container}-{size}-{type_name}"
        return f"scalar-{type_name}"
    return f"tuple-{len(descriptors)}"
