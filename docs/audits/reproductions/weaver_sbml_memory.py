"""Bounded offline XML parser memory measurement; no AGORA download required."""

import tempfile
import time
import tracemalloc
from pathlib import Path

from agora_weaver.dataset import iter_sbml_reactions

with tempfile.TemporaryDirectory() as directory:
    for count in (1000, 20000, 100000):
        path = Path(directory) / "model.xml"
        with path.open("w") as handle:
            handle.write("<sbml><model><listOfSpecies>")
            for index in range(count):
                handle.write(f'<species id="s{index}"><annotation>detail</annotation></species>')
            handle.write('</listOfSpecies><reaction id="R_one"/></model></sbml>')
        tracemalloc.start()
        start = time.perf_counter()
        with path.open("rb") as handle:
            reactions = sum(1 for _ in iter_sbml_reactions(handle))
        elapsed = time.perf_counter() - start
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        print(
            f"{count} species; {path.stat().st_size} bytes; {reactions} reaction; peak {peak} bytes; {elapsed:.3f}s"
        )
