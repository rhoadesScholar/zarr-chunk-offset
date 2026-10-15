Title: Offset chunk key encoding: grow an array in the negative direction by whole chunks

Registers the `offset` chunk key encoding: the `default` encoding applied to the chunk grid
coordinate plus a fixed per-dimension integer offset, so that adding `k` whole chunks before
array index 0 is two metadata edits (`shape[a] += k * chunk_shape[a]`, `offset[a] -= k`) and
no chunk changes its key.

Array indexing stays zero-based; `shape`, the `regular` chunk grid and the codecs keep their
meaning. With an all-zero offset the keys are byte-for-byte those of `default`. An
implementation that does not know the name refuses the array, which is why this is a new
encoding rather than a field on the `regular` grid (current readers would ignore such a field
and address every chunk from grid coordinate 0).

This is the chunk-level extension named as the alternative when zarr-specs#122 / #144 declined
a change to array indexing (@rabernat: "an optional extension that would operate at the chunk
level, i.e. creating chunks like `-1.0.0`"; @d-v-b: "explicitly tracking the name of the first
chunk in some metadata"), and the direction @jbms pointed at when closing zarr-specs#9. It
keeps to the one field it needs; sub-chunk growth and a user-facing non-zero array origin are
out of scope.

**What it costs today versus with the encoding.** Growing a `default`-encoded array by two
chunk rows in front, on one machine (NVMe, zarr-python 3.4.1), wall seconds:

| chunks (64³ uint8) | rename every chunk file | copy to a new array | `offset`: one `zarr.json` write |
|---:|---:|---:|---:|
| 512 | 0.03 | 0.32 | 0.004 |
| 4 096 | 0.13 | 3.1 | 0.006 |
| 32 768 (8 GiB) | 1.0 | 26.5 | 0.016 |

The rename column is the best case and only exists on a filesystem; on an object store the
rename is a copy + delete per chunk (44 s at 32 768 chunks through the zarr store API). The
`offset` column does not grow with the array. Script and raw rows:
https://github.com/rhoadesScholar/zarr-chunk-offset/tree/main/bench

**Implementations**

- zarr-python plugin, the reference: https://github.com/rhoadesScholar/zarr-chunk-offset
  (`zarr.chunk_key_encoding` entry point, zarr-python >= 3.1.3), with `adopt` and
  `prepend_chunks` and tests, including a metadata-only prepend on a copy of a real
  multiscale level.
- zarr-python core: `OffsetChunkKeyEncoding` plus `Array.prepend_chunks` / `Array.prepend`,
  branch https://github.com/rhoadesScholar/zarr-python/tree/offset-chunk-key-encoding
  (zarr-developers/zarr-python#<N>).
- tensorstore zarr3 driver: reads and writes it, including key-range deletion on shrink with
  negative key components,
  https://github.com/rhoadesScholar/tensorstore/tree/zarr3-offset-chunk-key-encoding
  (google/tensorstore#<N>).
- neuroglancer: reads it,
  https://github.com/rhoadesScholar/neuroglancer/tree/zarr-offset-chunk-key-encoding
  (google/neuroglancer#<N>).

Motivation: volumes assembled from parts that arrive over time in no fixed order (our case:
serial-section pages registered as they are imaged, where a page can land below pages already
rendered). Licensed under CC BY 3.0 as the registry requires.

cc @jbms @d-v-b @clbarnes
