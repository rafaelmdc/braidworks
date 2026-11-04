# QuickGO implementation

## Approved annotation scope and term relations — #206 / #207

Version 0.1.13 declares ECO evidence exact/descendant matching, aspect and qualifier
parameters. Omission preserves upstream retrieval scope. Explicit NOT annotations
remain raw evidence but are excluded from positive summaries/fan-out, correcting
the previous biological interpretation. Mixed polarity terms retain positive
membership and all evidence. Coverage records filters and polarity counts.

A requested relation group projects observed typed children/obsoletion from the
already acquired term response. It preserves raw term data, does not invent
parents or replacements, and requires no extra request. Reverse annotation
retrieval and independently sourced parent/history relations remain deferred.

Verification: 75 package tests passed, strict verification and six live checks
passed, including exact ECO/aspect/qualifier filtering and typed child relations.
Regression tests cover NOT-only/mixed evidence, bulk filters, duplicate detachment,
invalid namespace and unavailable relation/history fields.
