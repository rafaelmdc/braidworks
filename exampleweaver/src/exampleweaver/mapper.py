"""The single ``ExampleRecord -> WeaveResult`` mapper.

Every backend feeds results through this one function, so all backends emit
identical strand shapes. It emits exactly the externally-requested outputs and
reports ``computed_groups`` as the groups actually triggered.
"""

from __future__ import annotations

from braidworks.core import Capability, Strand, WeaveResult, WeaveStatus

from exampleweaver.intermediate import ExampleRecord


def map_record(
    record: ExampleRecord,
    *,
    capability: Capability,
    requested_outputs: frozenset[str],
    backend: str,
    weaver_version: str,
) -> WeaveResult:
    """Map a neutral record to a ``WeaveResult`` for the requested outputs."""
    computed_groups = capability.triggered_groups(requested_outputs)
    allowed = capability.outputs_to_compute(requested_outputs)
    provenance = (f"example:{backend}",)

    strands: list[Strand] = []
    errors: tuple[str, ...] = ()

    if record.error is not None:
        status = WeaveStatus.ERROR
        errors = (record.error,)
    elif not record.found:
        status = WeaveStatus.NO_MATCH
    else:
        status = WeaveStatus.OK
        for type_id, value in record.values.items():
            if type_id in allowed and value is not None:
                strands.append(Strand(type_id, value, provenance=provenance))

    return WeaveResult(
        capability_id=capability.id,
        weaver_version=weaver_version,
        backend_used=backend,
        computed_groups=computed_groups,
        status=status,
        strands=tuple(strands),
        errors=errors,
    )
