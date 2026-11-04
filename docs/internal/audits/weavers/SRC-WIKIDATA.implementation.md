# Wikidata implementation

## Approved stable identity and localized labels — #286

Version 0.1.9 adds exact P685 taxid resolution using existing bulk SPARQL and
direct QID description through bulk Wikibase entity retrieval. The mapper selects
the shared lookup mapper for exact entity records while retaining the resolver
mapper for name/taxid ambiguity. Entity projection is a small pure module, not
a new class hierarchy. Redirects/missing identities are correlated explicitly;
localized labels/descriptions retain requested/actual language and English
fallback. Wikipedia titles remain strictly English and all sitelinks are acquired
before counting. Existing name/rank behavior is preserved.

Verification: 54 package tests, strict and three live checks passed. Tests cover
redirect/missing QIDs, label/description fallback, duplicate P685 ambiguity, bulk
correlation, detached duplicate outputs and unsafe input rejection. A real
Q36341 Portuguese/English response subset is retained in the spec. Unqualified
non-English Wikipedia routing remains deliberately excluded.
