# Scaffold Python interfaces


`generate_files(spec, spec_toml=raw_text)` returns a deterministic mapping of relative
`Path` keys to artifact text without filesystem access. It validates the semantic spec
and preserves the raw spec exactly. `validate_files(files)` checks paths and Python/TOML
syntax without importing or executing generated code. These functions, `write_files`,
and the existing `scaffold` facade are exported by `weaverkit`.

`write_files(files, destination, force=False, format_output=True)` validates the whole
mapping and preflights every destination path before writing UTF-8 files. It rejects
traversal, symlinks and file/directory conflicts. Without force, any nonempty destination
is refused. Force overwrites generated files **including implemented backends**, while
retaining unrelated files. For implemented packages, generate into a scratch directory,
review the diff, and selectively copy vocab/merge additions as described in
[the extension guide](safe-regeneration.md). Never force-regenerate in place. Formatting is optional
and best effort, after successful writes.

Validation and preflight failures leave the destination untouched. The subsequent
multi-file write is not transactional: disk errors or interruption can leave partial
output, and write errors propagate to the caller. `scaffold` composes generation and
writing with its existing arguments and sorted returned paths.


