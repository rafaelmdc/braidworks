# Migrating to core 0.13

Core 0.13 adds shared tabular input parsing and request pacing. Weaverkit 0.5 adds
browser batch input and a POST streaming endpoint; existing GET streaming clients
continue to work. The eleven API weavers and braidworks-arq 0.2 require core 0.13.

`BRAIDWORKS_RATE_LIMITS` now means HTTP requests per second rather than input
identifiers per second. Reassess configured rates against provider policies. Redis
buckets have capacity one; workers sharing a bucket must use matching settings.
Distributed fan-out now splits budgeted batches evenly, preserving upstream bulk
requests. Third-party HTTP backends need the pacing seam before a matching rate rule
can be used. See [request pacing](request-pacing.md).

At the time of this release, publication and durable cache/resume were deferred.
Later releases added opt-in [cache and saved-run interfaces](persistence.md).
Publication and further persistence scope remain separate project decisions.
