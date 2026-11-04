# Wikipedia approved monthly series — #295

Version 0.1.8 adds a requested series/title provenance group using already
validated API bins and the local dump month. No additional API request is made;
subtotal/default measurement semantics are preserved, missing bins are not
zero-filled, and duplicate-query results are detached. Title provenance records
the supplied article key and explicitly states the redirect policy.

Verification: 39 package tests passed, two opt-in skips; strict verification and
two live tests passed.
