# Set HTTP request rates

Set explicit request rates when running the CLI, Python API or browser. Rates apply
to HTTP requests, not identifiers; one bulk request can serve many inputs.

## Set source rates

Set the environment variable in the shell that will run Braidworks:

```bash
export BRAIDWORKS_RATE_LIMITS='ncbi:api=3,uniprot:api=2'
```

This allows three NCBI API requests and two UniProt API requests per second, shared
across clients in that process. The first request can proceed immediately. Prefer
`weaver:api` rules so a local backend does not inherit an HTTP budget. Run your query
from the same shell. Choose rates according to the provider's policy and your account;
project defaults do not discover those limits.

Executor budgets take precedence over environment rules, which override source defaults.
Without an explicit rule, BacDive defaults to 2 requests/second, STRING to 1, and
NCBI/GTDB/Wikipedia to 5; other shipped API backends have no default rate. Setup/download
utilities outside backend execution are outside this budget.

## Coordinate worker processes

Local pacing does not coordinate separate processes or external tools. For distributed
workers, configure explicit rules consistently through the experimental
[arq adapter](../braidworks-arq/README.md). Its Redis buckets coordinate source/backend
budgets; conflicting rate/capacity settings fail. Coordinate fleet changes and allow
previous bucket keys to expire before changing shared rates.

For exact retry/redirect/polling accounting, cancellation, backend support and integration
contracts, see [pacing reference](reference/request-pacing.md).
