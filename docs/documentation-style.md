# Write documentation for the reader's task

For contributors editing Braidworks documentation. The [first-pass audit](audits/documentation-readability.md)
records the research and repository findings behind these conventions.

## Give each page one job

The README answers what the tool does, how its sources connect, and how to try it.
The index routes readers to tasks. Usage guides show working steps; architecture
explains relationships; reference pages hold exact contracts and options. Keep audit
records and proposals separate from instructions for current behavior.

## Put context before mechanics

Explain what the reader has, what they want, and why the result matters before
introducing commands or classes. Define unfamiliar terms where they first help.
Use a short successful path before showing exceptional cases. Put prerequisites
before code, and say whether a snippet is a complete script, notebook cell, or
fragment. Link to details rather than repeating them.

## Make scientific examples honest

Use real identifiers and declare source/setup requirements. Describe expected output
shape without presenting invented data or mutable counts as verified results. Explain
missing data, representative selections, source evidence, and ambiguity where they
affect interpretation. Preserve coverage rows in analysis examples.

## Keep guidance maintainable

Use `uv run --no-sync` after selected workspace installs. Check current command help,
public signatures, and generated catalogues before documenting behavior. Link to the
canonical reference instead of copying signatures or whole field lists into a guide.
If a detail must be duplicated, verify both locations in the same change.

Check local paths and heading anchors when moving content. Mark historical status
explicitly. A documentation-only edit normally needs example/link verification,
not a new runtime test suite. Reader testing is separate: ask someone to complete
the documented task and observe where the guide fails them.
