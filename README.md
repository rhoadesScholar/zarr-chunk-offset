# zarr-chunk-offset

The `offset` chunk key encoding for Zarr v3, as a zarr-python plugin, plus the two metadata
edits that grow an array in the negative direction by whole chunks without moving a byte.

## The problem

A Zarr v3 array addresses its chunks from array index 0 upward (`c/0/0/0`, `c/0/0/1`, ...).
`resize` moves the high edge; nothing moves the low one. Adding data *before* index 0 means
shifting every array index, which for a whole number of chunks is a rename of every chunk key
and for anything else a rewrite. Volumes that are assembled as their parts arrive, in no fixed
order, hit this constantly. The discussion goes back to
[zarr-specs#9](https://github.com/zarr-developers/zarr-specs/issues/9) (2018) and
[zarr-specs#122](https://github.com/zarr-developers/zarr-specs/issues/122); a change to array
indexing itself was declined there, and a chunk-level extension was the alternative its
reviewers named.

## The encoding

```json
"chunk_key_encoding": {
  "name": "offset",
  "configuration": {"separator": "/", "offset": [-3, 0, 0]}
}
```

A chunk at grid index `g` (per dimension) is stored under the key the `default` encoding gives
`g + offset`. `separator` is `/` or `.` as for `default`; `offset` holds one integer per array
dimension and may be negative. Array indexing is unchanged and zero-based; `shape` and the
`regular` chunk grid keep their meaning. With an all-zero `offset` the keys are byte-for-byte
those of `default` with the same separator.

Growing by `k` whole chunks in the negative direction of axis `a` is then two edits to the
array's metadata, written together:

```
shape[a]  += k * chunk_shape[a]
offset[a] -= k
```

Every existing chunk keeps its key: the chunk formerly at grid index `g` is now at `g + k`, and
its key is `(g + k) + (offset - k) = g + offset`. The new leading chunks take the keys of the
grid cells now in front, which may be negative (`c/-1/0/0`). A negative component is a legal
store key; stores that cannot carry a `-` can start from a large positive `offset` instead.

Readers without this encoding must refuse the array: the name is unknown to them and the
specification does not allow `must_understand: false` on a chunk key encoding, so there is no
silent misread. That is the reason it is a new name rather than a new key on the `regular` grid,
which current readers would ignore and then address every chunk wrongly.

## Use

```python
import zarr
from zarr_chunk_offset import adopt, prepend_chunks

a = zarr.open_array("volume.zarr/s0", mode="r+")   # a default-encoded v3 array
a = adopt(a)                                        # metadata only; no key changes
a = prepend_chunks(a, axis=0, n=3)                  # three chunk rows below index 0
a[: 3 * a.chunks[0]] = new_planes                   # lands in c/-3, c/-2, c/-1
```

Installing the package registers the encoding with zarr-python through the
`zarr.chunk_key_encoding` entry point, so `zarr.open` reads such an array with no further setup.

Physical coordinates are a separate layer. If the array carries a world position (an OME-NGFF
`translation`, funlib's `offset`), the writer moves it by `k * chunk * scale` in the same step
so array index 0 keeps describing the same place. For a multiscale group the prepend is
metadata-only at every level only when `k * chunk_s0 / downsample_i` is a whole number of level
`i` chunks; otherwise the coarser levels are rebuilt.

## Status

A proposal, with this package as the implementation the extension registry asks for. Nothing
is posted upstream yet; `campaign/` holds the PR bodies and the research behind the design.
Branches on forks carry the reader and writer changes:

| repo | branch | what |
|---|---|---|
| zarr-developers/zarr-extensions | [`chunk-key-encodings/offset`](https://github.com/rhoadesScholar/zarr-extensions/tree/chunk-key-encodings/offset) | the registry entry (`extension/` here is its source) |
| zarr-developers/zarr-python | [`offset-chunk-key-encoding`](https://github.com/rhoadesScholar/zarr-python/tree/offset-chunk-key-encoding) | `OffsetChunkKeyEncoding` in core, `Array.prepend` (the mirror of `append`) |
| google/tensorstore | [`zarr3-offset-chunk-key-encoding`](https://github.com/rhoadesScholar/tensorstore/tree/zarr3-offset-chunk-key-encoding) | zarr3 driver reads and writes it, key-range deletion with negative keys |
| google/neuroglancer | [`zarr-offset-chunk-key-encoding`](https://github.com/rhoadesScholar/neuroglancer/tree/zarr-offset-chunk-key-encoding) | reads it |

`bench/` measures what a growth costs today against the metadata edit (67× to 2 800× at
32 768 chunks, and the gap is the array size).

```
pip install zarr-chunk-offset
pytest
```
