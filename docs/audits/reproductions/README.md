# Retained individual-weaver audit reproductions

These scripts report current behavior; they are audit evidence, not contract tests or
fixes. Run from the repository root with the isolated workspace environment:

```bash
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_uniprot.py
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_ncbi_build.py
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_gtdb.py
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_bacdive.py
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_gut_sources.py
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_faprotax.py
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_mondo.py
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_wiki_sources.py
```

They use installed workspace packages, HTTP MockTransport and temporary directories;
no upstream requests, credential access, large downloads or user's database writes.
The destructive NCBI rebuild demonstration only overwrites its freshly created tiny
fixture. MONDO's cyclic query is interrupted with a bounded SQLite progress handler.
The gut script covers AGORA/Disbiome/GMrepo; wiki script covers Wikidata/Wikipedia.

Other focused probes/logs remain ignored under `.audit-local`; reports distinguish
code inspection, mocked source examples and bounded actual upstream GETs. A mocked
response demonstrates handling, not proof that upstream currently returns that shape.
All scripts checked with the existing Ruff executable. Findings refer to unchanged
source revision `d5e7543`; outputs should change when accepted fixes are implemented.

[Audit index](../weavers/README.md), [summary](../weavers/summary.md).

AGORA parser memory characterization (synthetic local XML, no downloads):

```bash
.audit-local/tools/venv/bin/python docs/audits/reproductions/weaver_sbml_memory.py
```

The script consumes reactions without retaining the parsed XML. It measures parser
allocations, not SQLite/native allocations or full-archive ingestion.

## FAPROTAX source differential

`python docs/audits/reproductions/faprotax_reference.py /path/to/collapse_table.py`
from the repo root compares the bundled database against the provider's 1.3.7 script,
shipped in the official FAPROTAX 1.2.12 archive. Requires only the installed local weaver
and stdlib. It loads named provider functions without executing the CLI or importing
numpy/BIOM. Keep downloaded provider software outside tracked files.

[Retained result](faprotax-reference-result.json): all 92 groups, 25,068 representative
source-pattern/binomial/false-positive cases, zero mismatches; the provider script's
SHA256 is recorded. This extends the original small grammar reproduction rather than
replacing the audit evidence with a claim of biological ground truth.
