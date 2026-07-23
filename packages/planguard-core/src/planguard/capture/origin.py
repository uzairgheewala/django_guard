"""Configurable Python application-origin capture."""

from __future__ import annotations

import fnmatch
import hashlib
import inspect
from pathlib import Path

from planguard.artifacts.models import OriginCaptureMode, QueryOrigin, SourceFrame
from planguard.canonical import canonical_json_bytes

_DEFAULT_EXCLUDES = (
    "planguard.*",
    "django.*",
    "pytest.*",
    "unittest.*",
    "contextlib",
)


def _frame(module: str | None, filename: str, line: int, function: str) -> SourceFrame:
    return SourceFrame(
        module=module,
        file=Path(filename).as_posix(),
        line=line,
        function=function,
    )


def capture_origin(
    *,
    mode: OriginCaptureMode,
    application_roots: tuple[str, ...],
    exclude_module_patterns: tuple[str, ...],
    max_stack_depth: int,
) -> QueryOrigin:
    if mode == OriginCaptureMode.NONE:
        return QueryOrigin()
    excludes = (*_DEFAULT_EXCLUDES, *exclude_module_patterns)
    captured: list[SourceFrame] = []
    first_application: SourceFrame | None = None
    stack = inspect.stack(context=0)[2 : 2 + max_stack_depth]
    try:
        for info in stack:
            module = info.frame.f_globals.get("__name__")
            module_name = module if isinstance(module, str) else None
            candidate = _frame(module_name, info.filename, info.lineno, info.function)
            excluded = any(
                module_name and fnmatch.fnmatch(module_name, pattern) for pattern in excludes
            )
            is_application = (
                not excluded
                and (
                    not application_roots
                    or any(
                        module_name == root or (module_name or "").startswith(f"{root}.")
                        for root in application_roots
                    )
                )
            )
            if is_application and first_application is None:
                first_application = candidate
            if mode == OriginCaptureMode.FULL_STACK:
                captured.append(candidate)
            elif mode == OriginCaptureMode.TRIMMED_APPLICATION_STACK and is_application:
                captured.append(candidate)
            elif mode == OriginCaptureMode.FIRST_APPLICATION_FRAME and first_application is not None:
                break
    finally:
        for info in stack:
            del info

    if mode == OriginCaptureMode.FIRST_APPLICATION_FRAME:
        captured = [first_application] if first_application else []
    material = [item.model_dump(mode="json") for item in captured]
    if first_application and not material:
        material = [first_application.model_dump(mode="json")]
    fingerprint = (
        f"stk_{hashlib.sha256(canonical_json_bytes(material)).hexdigest()}" if material else None
    )
    return QueryOrigin(
        application_frame=first_application,
        stack=tuple(item for item in captured if item is not None),
        stack_fingerprint=fingerprint,
    )
