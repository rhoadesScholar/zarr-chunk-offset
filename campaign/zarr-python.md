Title: Add the offset chunk key encoding and Array.prepend

Adds the `offset` chunk key encoding (zarr-developers/zarr-extensions#<N>): the `default` key
of `chunk_coords + offset`, one integer per dimension, any sign. Under it an array grows in
the negative direction of an axis by whole chunks as a metadata-only change, and
`Array.prepend_chunks(n_chunks, axis)` / `Array.prepend(data, axis)` do exactly that: `shape`
grows, `offset` drops, one `zarr.json` write, every existing chunk keeps its key.

```python
z = zarr.create_array(store, shape=(6, 4), chunks=(3, 4), dtype="int32",
                      chunk_key_encoding={"name": "offset", "offset": (0, 0)})
z[:] = 1
z.prepend(np.full((6, 4), 2, dtype="int32"))   # shape (12, 4); keys c/-2/0, c/-1/0, c/0/0, c/1/0
```

**Before / after.** Today the only ways to add data before index 0 touch every chunk: rename
each chunk key (filesystem only), get/set/delete each chunk through the store API, or copy the
array. Measured on one machine (NVMe, 64³ uint8 chunks, two chunk rows added in front):

| chunks | rename each file | store get/set/delete | copy to new array | `prepend_chunks` |
|---:|---:|---:|---:|---:|
| 512 | 0.03 s | 0.76 s | 0.32 s | 0.004 s |
| 4 096 | 0.13 s | 5.9 s | 3.1 s | 0.006 s |
| 32 768 (8 GiB) | 1.0 s | 44 s | 26 s | 0.016 s |

Script: https://github.com/rhoadesScholar/zarr-chunk-offset/tree/main/bench. The test
`test_prepend_chunks_is_a_metadata_only_edit` asserts the property directly: the store's key
set is unchanged across the growth.

**Design**

- `OffsetChunkKeyEncoding(offset, separator="/")` in `zarr.core.chunk_key_encodings`,
  registered as `"offset"`. The offset length is checked against the shape when
  `ArrayV3Metadata` is built, so a wrong-rank offset fails at creation, not at the first key.
- The `ChunkKeyEncodingParams` shortcut (`{"name": ..., "separator": ...}`) now carries
  `offset` into the configuration; before, that branch rebuilt the configuration with only
  `separator`.
- `prepend_chunks` refuses an array on `default` or `v2` with a `TypeError` that names the
  encoding, rather than renaming chunks behind the caller's back; switching an existing array
  is a one-line metadata rewrite that the plugin's `adopt` performs and that could become a
  core helper later.
- Readers without the encoding refuse the array (unknown name; `must_understand` cannot be
  false for a chunk key encoding), which is the reason this is a new name and not a field on
  the regular grid.

Tests: 28 new (encoding round trips, negative components, rank checks, the shortcut, prepend,
prepend_chunks, refusals); `tests/test_array.py`, `tests/test_metadata`, `tests/test_api` and
`tests/test_chunk_key_encodings.py` pass (3056 passed); mypy and ruff clean. Docs: a
"Growing before index 0" section in the arrays guide and a changelog fragment.

Related: zarr-specs#9, zarr-specs#122.
