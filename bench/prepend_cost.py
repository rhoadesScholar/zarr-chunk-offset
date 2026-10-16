"""What it costs to grow a Zarr v3 array in the negative direction, before and after ``offset``.

Before: the array keeps the ``default`` encoding, so adding ``k`` whole chunks in front of axis
0 means every existing chunk moves to a new key. Three ways to do that today, all of which touch
every chunk:

* ``rename``  - ``os.rename`` each chunk file (filesystem stores only; the cheapest possible
  path, and still one syscall per chunk, high index first so no key is overwritten)
* ``set-del`` - ``store.get`` + ``store.set`` under the new key + ``store.delete`` of the old
  one through the zarr store API (what an object store makes you do: copy + delete)
* ``copy``    - create a new array of the grown shape and copy the data across (what most code
  does today)

After: ``adopt`` once (one ``zarr.json`` write, no key changes), then ``prepend_chunks`` is one
``zarr.json`` write per growth and no chunk is touched.

Usage::

    python bench/prepend_cost.py [--root DIR] [--chunks N ...] [--k K] [--methods ...]

Prints one row per (store, chunk count, method) with wall time and the number of store keys
touched. Chunk payload is ``chunk_bytes`` of random uint8 so compression does not collapse it.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np
import zarr
from zarr.core.buffer import default_buffer_prototype
from zarr.core.sync import sync
from zarr.storage import LocalStore, MemoryStore

from zarr_chunk_offset import adopt, prepend_chunks

CHUNK = (64, 64, 64)


def make_array(store, n_chunks: int, seed: int = 0) -> zarr.Array:
    """``n_chunks`` chunks laid out as ``(n0, 8, 8)`` chunk grid, every chunk written."""
    n0 = max(1, n_chunks // 64)
    shape = (n0 * CHUNK[0], 8 * CHUNK[1], 8 * CHUNK[2])
    a = zarr.create_array(store=store, shape=shape, chunks=CHUNK, dtype="uint8", fill_value=0,
                          compressors=None, overwrite=True)
    rng = np.random.default_rng(seed)
    for i in range(n0):
        a[i * CHUNK[0]:(i + 1) * CHUNK[0]] = rng.integers(0, 255, (CHUNK[0],) + shape[1:], dtype=np.uint8)
    return a


def chunk_keys(store) -> list[str]:
    async def _list():
        return [k async for k in store.list()]
    return [k for k in sync(_list()) if k != "zarr.json"]


def _grid(a: zarr.Array) -> tuple[int, ...]:
    return tuple(-(-s // c) for s, c in zip(a.shape, a.chunks, strict=True))


def before_rename(a: zarr.Array, k: int, root: Path) -> int:
    """Filesystem only: resize, then os.rename every chunk, highest first."""
    n0, n1, n2 = _grid(a)
    a.resize((a.shape[0] + k * a.chunks[0],) + a.shape[1:])
    moved = 0
    for i in range(n0 - 1, -1, -1):
        for j in range(n1):
            for l in range(n2):
                src = root / "c" / str(i) / str(j) / str(l)
                dst = root / "c" / str(i + k) / str(j) / str(l)
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.rename(src, dst)
                moved += 1
    return moved


def before_set_delete(a: zarr.Array, k: int) -> int:
    """Any store: resize, then get/set/delete every chunk through the store API."""
    n0, n1, n2 = _grid(a)
    store = a.store
    proto = default_buffer_prototype()
    a.resize((a.shape[0] + k * a.chunks[0],) + a.shape[1:])
    moved = 0
    for i in range(n0 - 1, -1, -1):
        for j in range(n1):
            for l in range(n2):
                src, dst = f"c/{i}/{j}/{l}", f"c/{i + k}/{j}/{l}"
                buf = sync(store.get(src, prototype=proto))
                sync(store.set(dst, buf))
                sync(store.delete(src))
                moved += 1
    return moved


def before_copy(a: zarr.Array, k: int, store_factory) -> int:
    """Any store: a new array of the grown shape, data copied across chunk row by chunk row."""
    new_store = store_factory("grown")
    b = zarr.create_array(store=new_store, shape=(a.shape[0] + k * a.chunks[0],) + a.shape[1:],
                          chunks=a.chunks, dtype=a.dtype, fill_value=0, compressors=None,
                          overwrite=True)
    n0 = _grid(a)[0]
    for i in range(n0):
        b[(i + k) * a.chunks[0]:(i + k + 1) * a.chunks[0]] = a[i * a.chunks[0]:(i + 1) * a.chunks[0]]
    return n0 * _grid(a)[1] * _grid(a)[2]


def after_offset(a: zarr.Array, k: int) -> int:
    a = adopt(a)
    prepend_chunks(a, axis=0, n=k)
    return 0


def after_bounded(a: zarr.Array, k: int) -> int:
    """The metadata step of `Array.prepend` under the `regular_bounded` chunk grid: one
    zarr.json write that switches the grid and moves the lower bound."""
    store = a.store
    proto = default_buffer_prototype()
    meta = json.loads(sync(store.get("zarr.json", prototype=proto)).to_bytes())
    n = k * a.chunks[0]
    meta["shape"][0] += n
    meta["chunk_grid"] = {
        "name": "regular_bounded",
        "configuration": {
            "chunk_shape": meta["chunk_grid"]["configuration"]["chunk_shape"],
            "origin": [0] * len(meta["shape"]),
            "lower_bound": [-n] + [0] * (len(meta["shape"]) - 1),
        },
    }
    sync(store.set("zarr.json", proto.buffer.from_bytes(json.dumps(meta).encode())))
    return 0


def run(store_kind: str, n_chunks: int, k: int, methods: list[str], root: Path) -> list[dict]:
    rows = []
    for method in methods:
        if store_kind == "memory":
            if method == "rename":
                continue
            factory = lambda name: MemoryStore()
            store = factory("a")
            arr_root = None
        else:
            base = root / f"{store_kind}-{n_chunks}-{method}"
            shutil.rmtree(base, ignore_errors=True)
            base.mkdir(parents=True)
            factory = lambda name, base=base: LocalStore(base / name)
            store = factory("a")
            arr_root = base / "a"
        a = make_array(store, n_chunks)
        keys_before = chunk_keys(a.store)
        t0 = time.perf_counter()
        if method == "rename":
            touched = before_rename(a, k, arr_root)
        elif method == "set-del":
            touched = before_set_delete(a, k)
        elif method == "copy":
            touched = before_copy(a, k, factory)
        elif method == "offset":
            touched = after_offset(a, k)
        elif method == "bounded":
            touched = after_bounded(a, k)
        else:
            raise SystemExit(f"unknown method {method}")
        dt = time.perf_counter() - t0
        if method in ("offset", "bounded"):
            assert chunk_keys(a.store) == keys_before, f"{method} moved a chunk key"
        rows.append({"store": store_kind, "chunks": len(keys_before), "k": k, "method": method,
                     "seconds": round(dt, 4), "keys_touched": touched})
        print(json.dumps(rows[-1]), flush=True)
        if store_kind != "memory":
            shutil.rmtree(base, ignore_errors=True)
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--root", type=Path, default=None, help="directory for the local stores (default: a temp dir)")
    p.add_argument("--chunks", type=int, nargs="+", default=[64, 512, 4096])
    p.add_argument("--k", type=int, default=2, help="chunks to add in front of axis 0")
    p.add_argument("--stores", nargs="+", default=["memory", "local"])
    p.add_argument("--methods", nargs="+", default=["rename", "set-del", "copy", "bounded"])
    p.add_argument("--json", type=Path, default=None, help="append rows here")
    args = p.parse_args()
    root = args.root or Path(tempfile.mkdtemp(prefix="prepend-bench-"))
    rows = []
    for store_kind in args.stores:
        for n in args.chunks:
            rows += run(store_kind, n, args.k, args.methods, root)
    if args.json:
        with args.json.open("a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    print()
    print(f"{'store':8} {'chunks':>7} {'method':8} {'seconds':>10} {'keys touched':>13}")
    for r in rows:
        print(f"{r['store']:8} {r['chunks']:7d} {r['method']:8} {r['seconds']:10.4f} {r['keys_touched']:13d}")


if __name__ == "__main__":
    main()
