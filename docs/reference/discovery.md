# Weaver discovery

Core discovers installed source adapters from the `braidworks.weavers` entry-point
group. For ordinary query use, see [usage](../usage.md); for package boundaries,
see [architecture](../architecture.md).

## Strict and tolerant inventories

Discovery (`build_registry_from_entry_points`) loads every installed weaver from the
`braidworks.weavers` entry-point group, so the CLI and an arq worker share one mechanism.
It is strict: a selected plugin failure raises the original exception, with a note naming
its entry point and failing stage. `only=frozenset({...})` filters names before importing.

For a partial inventory, call `discover_registry(policy=DiscoveryPolicy.TOLERANT)`.
The report contains a fresh `registry` and `failures` with the entry-point name/value,
`load`/`build`/`register` stage, exception type and message. `DiscoveryFailure` supports
`to_json()`/`from_json()`; live registry instances are not serialized. Tolerant discovery
continues after per-plugin failures; metadata enumeration and process-control exceptions
still propagate. Core does not cache registries; arq owns its worker-local cache.

## Toolkit and workers

The network view and references command use tolerant core discovery: a broken plugin
is skipped and reported as `name: ExceptionType: message`, while valid plugins remain
available. Query and worker discovery raise selected plugin failures.
`weaverkit.view.discover_registry(only=frozenset({...}))` filters before importing.

Implementation: [core discovery](../../braidworks-core/src/braidworks/core/discovery.py).
