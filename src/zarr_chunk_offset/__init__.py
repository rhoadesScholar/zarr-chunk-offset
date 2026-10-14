"""The ``offset`` chunk key encoding for Zarr v3.

A chunk at grid index ``g`` is stored under the key the ``default`` encoding would give
``g + offset``. Array indexing is unchanged and zero-based; only the mapping from chunk grid
coordinates to store keys moves. Growing the array by ``k`` whole chunks in the negative
direction of an axis is then two edits to ``zarr.json``: ``shape[axis] += k * chunk_shape[axis]``
and ``offset[axis] -= k``. Every existing chunk keeps its key, and the new chunks take the keys
of the grid cells now in front of it, which may be negative (``c/-1/0``).

With an all-zero ``offset`` the encoding is byte-for-byte the ``default`` encoding, so an
existing array can adopt it without moving a chunk (:func:`adopt`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, ClassVar

import zarr
from zarr.abc.store import Store
from zarr.core.buffer import default_buffer_prototype
from zarr.core.chunk_key_encodings import (
    ChunkKeyEncoding,
    DefaultChunkKeyEncoding,
    SeparatorLiteral,
    parse_separator,
)
from zarr.core.sync import sync
from zarr.registry import register_chunk_key_encoding

__all__ = ["OffsetChunkKeyEncoding", "adopt", "prepend_chunks", "NAME"]

NAME = "offset"


@dataclass(frozen=True)
class OffsetChunkKeyEncoding(ChunkKeyEncoding):
    """``default`` keys of ``chunk_coords + offset``.

    ``offset`` has one integer per array dimension (an empty tuple means all zeros, which makes
    this encoding identical to ``default`` with the same separator). Values may be negative.
    """

    name: ClassVar[str] = NAME
    separator: SeparatorLiteral = "/"
    offset: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "separator", parse_separator(self.separator))
        offset = tuple(int(o) for o in self.offset)
        if any(int(o) != o for o in self.offset):
            raise ValueError(f"offset must hold integers, got {self.offset!r}")
        object.__setattr__(self, "offset", offset)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "configuration": {"separator": self.separator, "offset": list(self.offset)},
        }

    def _base(self) -> DefaultChunkKeyEncoding:
        return DefaultChunkKeyEncoding(separator=self.separator)

    def _shift(self, coords: tuple[int, ...], sign: int) -> tuple[int, ...]:
        if self.offset and len(self.offset) != len(coords):
            raise ValueError(
                f"offset has {len(self.offset)} dimensions but the chunk coordinates have "
                f"{len(coords)}: {coords!r}")
        offset = self.offset or (0,) * len(coords)
        return tuple(int(c) + sign * o for c, o in zip(coords, offset, strict=True))

    def encode_chunk_key(self, chunk_coords: tuple[int, ...]) -> str:
        return self._base().encode_chunk_key(self._shift(chunk_coords, +1))

    def decode_chunk_key(self, chunk_key: str) -> tuple[int, ...]:
        if chunk_key == "c":
            return self._shift((), -1)
        prefix = "c" + self.separator
        if not chunk_key.startswith(prefix):
            raise ValueError(f"not an offset-encoded chunk key: {chunk_key!r}")
        coords = tuple(int(part) for part in chunk_key[len(prefix):].split(self.separator))
        return self._shift(coords, -1)


register_chunk_key_encoding(NAME, OffsetChunkKeyEncoding)


def _metadata_key(array: zarr.Array) -> str:
    return f"{array.path}/zarr.json" if array.path else "zarr.json"


def _read_metadata(store: Store, key: str) -> dict[str, Any]:
    buf = sync(store.get(key, prototype=default_buffer_prototype()))
    if buf is None:
        raise FileNotFoundError(key)
    return json.loads(buf.to_bytes())


def _write_metadata(store: Store, key: str, meta: dict[str, Any]) -> None:
    data = json.dumps(meta, indent=2).encode()
    sync(store.set(key, default_buffer_prototype().buffer.from_bytes(data)))


def _require_v3(meta: dict[str, Any], what: str) -> None:
    if meta.get("zarr_format") != 3 or meta.get("node_type") != "array":
        raise ValueError(f"{what}: only Zarr v3 arrays carry a chunk key encoding")
    grid = meta.get("chunk_grid", {})
    if grid.get("name") != "regular":
        raise ValueError(f"{what}: the chunk grid must be `regular`, got {grid.get('name')!r}")


def adopt(array: zarr.Array) -> zarr.Array:
    """Switch an array from the ``default`` encoding to ``offset`` with all-zero offsets.

    Metadata only: no chunk moves, and every key stays what it was. Returns the array re-opened
    on the new metadata. An array already on ``offset`` is returned re-opened, unchanged.
    """
    key = _metadata_key(array)
    meta = _read_metadata(array.store, key)
    _require_v3(meta, "adopt")
    cke = meta.get("chunk_key_encoding", {"name": "default"})
    if cke.get("name") == NAME:
        return zarr.open_array(store=array.store, path=array.path, mode="r+")
    if cke.get("name") != "default":
        raise ValueError(
            f"adopt: only a `default`-encoded array can adopt `offset` without moving chunks; "
            f"this one is {cke.get('name')!r}")
    separator = (cke.get("configuration") or {}).get("separator", "/")
    meta["chunk_key_encoding"] = OffsetChunkKeyEncoding(
        separator=separator, offset=(0,) * len(meta["shape"])).to_dict()
    _write_metadata(array.store, key, meta)
    return zarr.open_array(store=array.store, path=array.path, mode="r+")


def prepend_chunks(array: zarr.Array, axis: int, n: int) -> zarr.Array:
    """Grow ``array`` by ``n`` whole chunks in the negative direction of ``axis``.

    Two metadata edits and nothing else: ``shape[axis]`` grows by ``n * chunk_shape[axis]`` and
    ``offset[axis]`` drops by ``n``. Existing chunks keep their keys; the new leading chunks are
    unwritten and read as the fill value until written. The array must use the ``offset``
    encoding (see :func:`adopt`). Returns the array re-opened on the new metadata.

    The two edits are one ``zarr.json`` write, so a reader never sees one without the other;
    a writer racing this call on the same array is the caller's problem, as for ``resize``.
    """
    if n < 0:
        raise ValueError(f"n must be >= 0, got {n}")
    key = _metadata_key(array)
    meta = _read_metadata(array.store, key)
    _require_v3(meta, "prepend_chunks")
    cke = meta.get("chunk_key_encoding", {})
    if cke.get("name") != NAME:
        raise ValueError(
            f"prepend_chunks: the array uses the {cke.get('name')!r} chunk key encoding; adopt "
            f"`offset` first (zarr_chunk_offset.adopt), which moves no chunk")
    ndim = len(meta["shape"])
    if not 0 <= axis < ndim:
        raise ValueError(f"axis {axis} out of range for a {ndim}-D array")
    if n == 0:
        return zarr.open_array(store=array.store, path=array.path, mode="r+")
    chunk = int(meta["chunk_grid"]["configuration"]["chunk_shape"][axis])
    config = dict(cke.get("configuration") or {})
    offset = list(config.get("offset") or [0] * ndim)
    offset[axis] -= n
    shape = list(meta["shape"])
    shape[axis] += n * chunk
    meta["shape"] = shape
    meta["chunk_key_encoding"] = OffsetChunkKeyEncoding(
        separator=config.get("separator", "/"), offset=tuple(offset)).to_dict()
    _write_metadata(array.store, key, meta)
    return zarr.open_array(store=array.store, path=array.path, mode="r+")
