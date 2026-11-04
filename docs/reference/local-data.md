# Local-data generations and build ownership

Contracts for operating local SQLite source artifacts. For NCBI acquisition steps,
see [database setup](../database.md).

## Reader generations and build ownership


Local SQLite backends bind to one generation of the artifact. Fingerprints include
source metadata and local file-generation stamps; GTDB also includes its tree files.
If the database/tree changes, reopen the weaver instead of reusing a backend whose
fingerprint describes another generation. Legacy file stamps are local replacement
guards, not portable checksums. New builders record schema/build identity alongside
available release/content metadata. No large-file hash is computed per lookup.
Batch connections close when work completes. Synchronous batch work runs in threads;
cancellation stops awaiting it but does not terminate an already-running thread.

Builds use local OS advisory locks (POSIX/Windows) and atomic publication. The small
`.lock` file intentionally remains after release; the kernel owns the active lock.
Do not delete it while builds may be running. BuildLock accepts a bounded acquisition
timeout and optional wait callback. Process exit releases ownership automatically.

## NCBI reviewed-history storage

TaxonomyResolverService opens reference data read-only. Its default reviewed-history
path is `<taxonomy filename>.reviews.sqlite` beside the reference database. Pass
`cache_db_path` to choose another writable local location. This is user-authored
history, independent of the executor's lookup cache.

On open, legacy colocated reviewed_mappings are copied transactionally to the separate
store. Repeated migration does not duplicate rows; failed imports roll back and leave
the original untouched. Copies retain the existing conservative reference-build/name/
level matching rules. Reference refresh keeps the separate history file; decisions from
another build remain stored but are not automatically reused.

For rollback to older software, retain the original reference/history artifact. New
reviews live in the separate file and can be used by older constructors via explicit
`cache_db_path`; do not delete either copy. An explicit same-reference cache path remains
a legacy compatibility option, but writes then invalidate a pinned local backend and
require reopening. Shared read-only reference installations should provide a writable
review path explicitly. Neither file belongs in git.


Implementation: [source binding](../../braidworks-core/src/braidworks/core/source_identity.py),
[acquisition and locks](../../braidworks-core/src/braidworks/core/localdb.py).

## Acquisition progress and network waits

Shared local-data setup reports acquisition/build stages and lock waits to stderr.
Downloads without a progress callback announce the request before connecting, then
report byte counts at most once every ten seconds and on completion or failure.
Existing valid artifacts remain silent. stdout stays available for query results.

`braidworks.core.localdb.download(..., progress=callback, timeout=30)` accepts a
replacement callback; use `progress=lambda *event: None` for quiet downloads.
`ensure_local_db(..., progress=callback)` similarly replaces its stage/lock events;
a source build callback controls progress for downloads it calls separately.
The download timeout must be finite and positive. It bounds socket inactivity,
including connection/read waits, rather than the total duration of a large transfer.
Optional checksum requests use the same 30-second socket limit. There are no automatic
retries in these helpers. Build-lock waits have their own finite timeout; a source's
parsing/build callback has no imposed total deadline.
