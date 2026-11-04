# Migrating to core 0.12

Ambiguous resolver matches now pause for review by default. Earlier candidate-bearing
results could automatically select or expand a match under the default HALT policy.
The new behavior applies to ordinary execution, traversal preludes, cached results,
the CLI, convenience fetch calls, and the browser.

Unambiguous lookup results and fan-out over known identifier sets behave as before.

## Python

The default executor policy is ReviewPolicy.HALT. Inspect result.review_queue:
each item preserves the original input, triggering candidates, and remaining steps.
For a reviewed choice, use the chosen identifier as the next input and request the
remaining target fields.

Automated workflows can explicitly select candidates:

    from braidworks.core import ExpandPolicy, ReviewPolicy

    result = await executor.execute(
        braid,
        inputs,
        review_policy=ReviewPolicy.ALLOW_CONTINUE,
        expand_policy=ExpandPolicy.top(),
        confidence_threshold=0.8,
    )

Positive confidence thresholds apply to candidate scores and selected strand scores.
Results below the floor pause even with ALLOW_CONTINUE. RAISE fails immediately.
Automatic selections preserve requires_review; callers must retain that metadata.

fetch()/async_fetch() accept the same review_policy and confidence_threshold controls.
FetchResult.review_queue preserves candidate context, and review_required lists IDs
that need curation, including explicitly selected ambiguous matches. Such paused IDs
also remain in unresolved because they produced no requested value. Both fields
round-trip through to_json()/from_json(); older JSON remains readable.

## CLI

The default is --review-policy halt. Machine exports include review rows and candidates.
To permit selection explicitly, add --review-policy allow_continue. For example:

    braidworks weave --have organism.name='an ambiguous name' \
      --want ncbi.taxon.id --review-policy allow_continue --confidence-threshold 0.8

--expand controls cardinality; it does not authorize ambiguity. --strict returns a
nonzero exit for queued reviews and resolved selections that still require review.
Without --strict, a review row is a reported outcome rather than a structural error.

## Browser

The shared Ambiguous matches control defaults to pause for review. It applies to
typed and graph runs, including pass-through traversal. Minimum confidence is
editable next to it. Results and JSON downloads display the effective policy/floor,
and saved recipes and generated CLI/Python code preserve them.

Existing recipes without these fields use the new safe defaults. Selecting the
automatic option is an explicit decision; an old expansion setting alone does not
imply consent to select ambiguous matches.


## Distributed execution with arq 0.1.6

Upgrade orchestrators and workers together. Executor jobs now include the expected
weaver manifest and backend fingerprint; mismatches abort as configuration errors
before a worker fetches data. Distributed caching is disabled by default. If deployment
controls guarantee matching manifests and datasets for the executor lifetime, opt in
with `build_distributed_executor(..., assume_homogeneous_workers=True)`. Passing a
custom cache without this assertion now raises a configuration error at construction.

The Redis budget now charges oversized batches in full instead of clamping them to a
single burst. Such batches can wait longer before dispatch. Refill uses Redis time;
invalid numeric rates fail explicitly. The budget counts inputs, not HTTP requests;
provider request pacing still needs backend-specific controls.
