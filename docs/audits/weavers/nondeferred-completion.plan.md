# Complete non-deferred weaver findings

User instruction: finish the issues, at least the non-deferred ones (2026-10-10).
This supersedes stopping after the approved minimum scopes. Complete outstanding
acceptance work and reconcile broad historical issue titles against delivered
behavior. Do not turn an explicit research deferral into silently approved scope.
#234, publishing #142 and durable cache/resume #143 remain excluded. Other
expansions explicitly deferred in recommendation-research.md stay identifiable.

| Issue | Outstanding action | Status |
|---|---|---|
| #219 | Reconcile completed supported parameters and scientific semantics | Verified; ready to close |
| #262 | Explicit exact-match organism/rank coverage; no ancestor inference | Implemented; 47 tests and strict pass |
| #298 | Verify pinned provider individual acquisition, or expose truthful unavailability | Research in progress |
| Remaining broad findings | Compare actual acceptance criteria with implementation; separate deferred residual scope | Pending |
| Source group / programme issues | Close only when all non-deferred acceptance work is evidenced; list deferred children | Pending |

Work stays on feat/weaver-audit-approved-scopes, with local commits and GitHub
updates. No push, release or tags. API changes need live checks; source acquisition
must not fall back to arbitrary mirrors or multi-GB downloads.
