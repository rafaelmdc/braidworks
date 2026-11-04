# Wikipedia proposed specification

Status proposed. [Evidence](wikipedia.audit.md).

| Finding | Acceptance |
|---|---|
| WV-WIKIPEDIA-001 | Each measurement exposes period/project/agent/access/coverage; API/local fulfill same requested metric or declare unsupported scope explicitly. |
| WV-WIKIPEDIA-002 | Twelve completed months selected with endpoint inclusivity accounted for; unexpected/duplicate/missing bins validated and coverage explicit. |
| WV-WIKIPEDIA-003 | Requested month checked against DB, mismatch actionable; source selection/prebuilt path/month config honored. |
| WV-WIKIPEDIA-004 | Valid zero, no data, partial and malformed response distinct; errors isolated per title, no raw JSON escape. |
| WV-WIKIPEDIA-005 | Distinct queries bounded/paced/ordered; explicit config/source identity/owned-client lifecycle and truthful UA. |
| WV-WIKIPEDIA-006 | Dump source hash/measurement descriptor and parser coverage recorded; invalid/negative counts rejected/diagnosed. |
| WV-WIKIPEDIA-007 | Conditional temporal series/params/title policy reviewed; correct usage/docs/safe regeneration. |

Preserve streaming ingestion/source-binding contracts. Public measurement descriptor JSON
round-trips; metric compatibility migration reviewed before changing legacy scalar/default.
No content scraping or arbitrary redirect aggregation. Version all accepted behavior sites.

Compatibility clarification (2026-10-08): the user permits necessary breaking changes.
Earlier preservation/default recommendations are revisable; prioritize correct, truthful
contracts and document affected interfaces, migration and version updates. Feature
proposals remain scope decisions. See the [issue hierarchy review](issue-hierarchy.md).
