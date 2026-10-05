# HTTP request pacing

Set `BRAIDWORKS_RATE_LIMITS` before running the CLI, Python API or browser:

```bash
export BRAIDWORKS_RATE_LIMITS='ncbi:api=3,uniprot:api=2'
```

Values are HTTP requests per second, not identifiers per second. Each configured
source/backend has a capacity-one bucket: the first request can run immediately,
then requests wait for tokens. Bulk lookups cost one token per upstream request;
pagination, polling, redirects and HTTP retries each cost another token. Failed
request attempts are charged. Existing client hooks and injected test clients work.

Local execution shares its budget across clients, threads and event loops in one
process. Independent processes need a shared worker service: `braidworks-arq` uses
Redis server time and one shared bucket per source/backend. Workers with conflicting
rate/capacity configurations fail explicitly; coordinate configuration changes across
the fleet and let previous bucket keys expire before changing the shared rate.

All eleven shipped API backend families support this seam. Third-party backends must
set `supports_request_pacing = True` and send every request through
`braidworks.core.http_pacing.PacedHTTPClient(client, weaver_id, backend)`; the keyless
HTTP scaffold includes this wiring. A matching rule for an unsupported backend raises
`BackendConfigurationError`. Prefer `weaver:api` rules so local database backends do
not accidentally inherit an HTTP budget.

Pacing is off unless configured. Choose rates according to the provider's policy and
your account; these controls do not discover provider limits. Setup/download utilities
outside backend execution are outside this budget. Cancellation interrupts pending
waits without sending another request. Separate local processes and external tools
are not coordinated by local pacing.
