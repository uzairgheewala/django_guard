"""Generic selector evaluation over canonical artifact data."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from planguard.artifacts.models import SelectorExpression, SelectorOperator
from planguard.canonical import canonical_data


class Missing:
    pass


MISSING = Missing()


def field_value(subject: Any, path: str) -> Any:
    current = canonical_data(subject) if isinstance(subject, BaseModel) else canonical_data(subject)
    for segment in path.split("."):
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return MISSING
        else:
            return MISSING
    return current


def _compare(operator: SelectorOperator, actual: Any, expected: Any) -> bool:
    if operator == SelectorOperator.EXISTS:
        return (actual is not MISSING) is bool(expected if expected is not None else True)
    if actual is MISSING:
        return False
    if operator == SelectorOperator.EQUALS:
        return actual == expected
    if operator == SelectorOperator.NOT_EQUALS:
        return actual != expected
    if operator == SelectorOperator.GREATER_THAN:
        return actual > expected
    if operator == SelectorOperator.GREATER_OR_EQUAL:
        return actual >= expected
    if operator == SelectorOperator.LESS_THAN:
        return actual < expected
    if operator == SelectorOperator.LESS_OR_EQUAL:
        return actual <= expected
    if operator == SelectorOperator.CONTAINS:
        try:
            return expected in actual
        except TypeError:
            return False
    if operator == SelectorOperator.IN_SET:
        try:
            return actual in expected
        except TypeError:
            return False
    raise ValueError(f"Unsupported selector operator: {operator}")


def matches(expression: SelectorExpression | None, subject: Any) -> bool:
    if expression is None:
        return True
    if expression.operator == SelectorOperator.ALL:
        return all(matches(child, subject) for child in expression.children)
    if expression.operator == SelectorOperator.ANY:
        return any(matches(child, subject) for child in expression.children)
    if expression.operator == SelectorOperator.NOT:
        return not matches(expression.children[0], subject)
    return _compare(
        expression.operator,
        field_value(subject, expression.field or ""),
        expression.value,
    )
