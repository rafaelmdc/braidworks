# BacDive implementation

## Approved strain list/describe — #246

Version 0.1.12 adds a registered integer BacDive strain bridge, complete observed
name-based ID listing and exact-ID description in 100-ID chunks. The existing
type-strain selection reuses the same listing without changing its behavior.
Exact descriptions preserve trait conflicts, source records, type/non-type
identity and observed culture collection/sequence references. They make no
species-wide inference. Core 0.21.8 declares the bridge's canonical integer type
and is the weaver dependency floor; toolkit 0.6.11 registers/catalogs the fields.

Verification: 64 package tests, strict and three live checks passed. A live
5621/unknown mixed fetch returns only 5621, confirming individual misses. Tests
assert one bulk request for several IDs, two chunks for 101 IDs, duplicate result
detachment and preservation of existing name-based behavior. Toolkit's 291 tests
pass with canonical/shared-key parity unchanged. Collection-number mapping stays
deferred.
