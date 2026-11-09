# Write documentation for the reader's task

For contributors editing Braidworks documentation. The [first-pass audit](../internal/audits/documentation-readability.md)
records the research and repository findings behind these conventions.

## Give each page one job

Use [Diátaxis](https://diataxis.fr/start-here/) to choose that job: a tutorial teaches
through a guided exercise, a how-to guide completes a task, reference supplies exact
facts, and explanation connects concepts and reasons. The
[documentation map](../internal/audits/documentation-diataxis.md) records the earlier
classification of existing pages.

Apply the guidance for the chosen type:

- [Tutorials](https://diataxis.fr/tutorials/): choose one concrete exercise, show visible
  results at each stage, and guide the reader through observations. Link alternatives
  and long explanations rather than interrupting the lesson.
- [How-to guides](https://diataxis.fr/how-to-guides/): state the task and prerequisites,
  then provide steps and relevant branches for someone already using the tool.
- [Reference](https://diataxis.fr/reference/): organize facts by the interface they
  describe. Keep exact defaults, fields and constraints findable and consistent.
- [Explanation](https://diataxis.fr/explanation/): connect concepts, consequences and
  reasons. Link instructions and exact contracts rather than embedding full workflows.

The README answers what the tool does, how its sources connect, and how to try it.
The index routes readers to tasks. Usage guides show working steps; architecture
explains relationships; reference pages hold exact contracts and options. Keep audit
records and proposals separate from instructions for current behavior.

## Where pages live

Each user page sits in the folder of its one type. The folders are the navigation.
(This replaces the October 2026 decision to keep URLs and express types only in the
index; see issue #306.)

| Folder | Type | Name pages as |
|---|---|---|
| `docs/tutorials/` | Tutorial | the exercise: `protein-structures.md` |
| `docs/how-to/` | How-to guide | the task, verb first: `cache-and-resume.md` |
| `docs/reference/` | Reference | the interface: `results.md`, `keys-index.md` |
| `docs/explanation/` | Explanation | the concept: `architecture.md` |
| `docs/internal/` | Project records | plans, audits, roadmaps; not user instructions |

The [documentation site](https://rafaelmdc.github.io/braidworks/) publishes these four
folders with the types as its top-level navigation. Add every new page to `nav` in
`mkdocs.yml`; a test fails while a public page is missing from it. `make docs-site`
builds the site strictly (a broken link or anchor fails) and `make docs-serve` previews
it. Links may point anywhere in the repository: the site rewrites links that leave
the published folders to the same file on GitHub.

A page that mixes types moves to its main type and gets split when it is next
rewritten. When you move a page, update every link to it in the same change (no stubs
at old paths); `make links-check` finds any you missed. Generated files (`reference/keys-index.md`,
`reference/weavers-index.tsv`) are rebuilt with `make index`, never edited by hand.

## Page templates

Start a new page from the template for its type, then delete what does not apply.

**Tutorial**

```markdown
# <What the reader will make>

<One paragraph: what you will produce and why it is useful.>

## Before you start
<Prerequisites, with links; the exact install command.>

## <Step named by its visible result>
<Command or code> → <what you should see>. <One sentence on what it means.>

## What you made
<Recap; where to go next: related how-to guides and explanation.>
```

**How-to guide**

```markdown
# <Verb-first task, e.g. "Cache lookups and resume a run">

<One sentence: when you need this. Prerequisites.>

## <Step or variant>
<Steps; branches for common variations.>

## Check it worked
<How to confirm; link reference for exact options.>
```

**Reference**

```markdown
# <Interface name>

<One sentence: what this describes and how it is generated or verified.>

| Name | Type / values | Default | Meaning |
|---|---|---|---|
```

**Explanation**

```markdown
# <Concept, e.g. "How routes are planned">

<The question this answers and why it matters to a user.>

## <Idea>
<Reasons, trade-offs, consequences; link the how-to and reference pages.>
```

## Review checklist

- [ ] The page does one job and lives in that type's folder.
- [ ] A tutorial produces something visible at every step and runs as written.
- [ ] A how-to guide starts from a task a user already has.
- [ ] Reference is complete for its interface and matches the code (generated where possible).
- [ ] Explanation contains no step-by-step instructions.
- [ ] `make links-check` passes.

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

Keep details that affect a choice, action, interpretation or recovery. Move useful
facts to the appropriate page and link them; remove filler and obsolete claims after
checking their replacements. Preserve prerequisites, defaults, limitations and side
effects. Reducing length is useful only when the reader can still complete the task.

Install with `uv sync --all-extras` and run with `uv run`; never document per-package
`uv sync --package` selections, because each one removes the packages it does not name.
Check current command help, public signatures, and generated catalogues before
documenting behavior. Link to the canonical reference instead of copying signatures or
whole field lists into a guide.
If a detail must be duplicated, verify both locations in the same change.

`make links-check` verifies local paths and heading anchors; CI runs it. Mark
historical status explicitly. A documentation-only edit normally needs example/link verification,
not a new runtime test suite. Reader testing is separate: ask someone to complete
the documented task and observe where the guide fails them.
