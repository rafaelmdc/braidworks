"""Unit checks for the taxonomy build CLI helper behavior."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from taxonomy_tools.build_ncbi_taxonomy import download_taxdump


class BuildNcbiTaxonomyCliTests(unittest.TestCase):
    """Validate the optional download helper without making network calls."""

    def test_download_taxdump_writes_response_bytes_to_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "downloads" / "taxdump.tar.gz"
            payload = b"fake-tarball-bytes"
            progress_buffer = io.StringIO()

            with patch(
                "taxonomy_tools.build_ncbi_taxonomy.urllib.request.urlopen",
                return_value=_FakeResponse(payload, content_length=len(payload)),
            ):
                download_taxdump(
                    "https://example.invalid/taxdump.tar.gz",
                    destination,
                    progress_stream=progress_buffer,
                    chunk_size=4,
                )

            self.assertEqual(destination.read_bytes(), payload)
            self.assertIn("100.0%", progress_buffer.getvalue())

    def test_download_taxdump_handles_missing_content_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            destination = Path(tmpdir) / "downloads" / "taxdump.tar.gz"
            payload = b"fake-tarball-bytes"
            progress_buffer = io.StringIO()

            with patch(
                "taxonomy_tools.build_ncbi_taxonomy.urllib.request.urlopen",
                return_value=_FakeResponse(payload),
            ):
                download_taxdump(
                    "https://example.invalid/taxdump.tar.gz",
                    destination,
                    progress_stream=progress_buffer,
                    chunk_size=5,
                )

            self.assertEqual(destination.read_bytes(), payload)
            self.assertIn("complete:", progress_buffer.getvalue())


class _FakeResponse:
    """Minimal context manager used to stub urllib responses in tests."""

    def __init__(self, payload: bytes, content_length: int | None = None) -> None:
        self._payload = payload
        self._offset = 0
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        """Provide a file-like read interface for `shutil.copyfileobj`."""

        if size == -1:
            size = len(self._payload) - self._offset
        start = self._offset
        end = min(len(self._payload), self._offset + size)
        self._offset = end
        return self._payload[start:end]
