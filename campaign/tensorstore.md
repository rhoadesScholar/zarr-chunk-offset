Title: zarr3: support the offset chunk key encoding

Adds the `offset` chunk key encoding (zarr-developers/zarr-extensions#80) to the zarr3
driver: the `default` key of `grid_index + offset`, one integer per dimension, any sign. It
lets an array grow in the negative direction of a dimension by whole chunks as a
metadata-only change (`shape` grows, `offset` drops; every existing chunk keeps its key), which
is the operation the zarr-python side exposes as `Array.prepend`.

```json
"chunk_key_encoding": {"name": "offset", "configuration": {"offset": [-2, 0, 0]}}
```

**Before / after.** Before: `Open` of such an array fails with an unknown-encoding error.
After: it opens, reads and writes; the test
`OffsetGrowsInTheNegativeDirectionWithoutMovingChunks` writes a `default` array, rewrites only
`zarr.json` (`shape` 6 → 12, encoding `offset [-2]`), reopens, and reads the old data at
`[6:12]` with the fill value in front, then writes `[0:3]` and lists the keys: `c/-2`, `c/0`,
`c/1`. No chunk moved.

**Changes**

- `ChunkKeyEncoding` gains `kOffset` and an `offset` vector; the JSON binder requires
  `offset` for that kind and rejects it for the others; `ValidateMetadata` checks its length
  against the rank (the binder does not know the rank).
- `FormatKey`, `GetChunkStorageKey` add the offset; `ParseKey` accepts a leading `-` under this
  encoding (rejecting `-0`) and subtracts it.
- `MinGridIndexForLexicographicalOrder`: keys hold `grid_index + offset`; a negative value
  sorts before every non-negative one but negatives do not sort numerically among themselves,
  so every grid index with a negative key is split off singly and the non-negative keys follow
  the base-10 digit-count rule shifted back into grid coordinates. The test
  `OffsetResizeDeletesOnlyTheChunksOutsideTheNewShape` exercises this through `Resize`.
- Schema docs: `driver/zarr3/ChunkKeyEncoding.offset`.
- Not changed: `GetResizedMetadata` still requires `inclusive_min == 0`; the growth itself is
  a metadata edit the writer performs, as in the test.

Tests: `metadata_test` (round trip, default separator, rank mismatch, missing/misplaced
`offset`, equality) and `driver_test` (keys at rank 1/2, `.` separator, zero offset equals
`default`, read-back, the growth, the resize). `bazel test //tensorstore/driver/zarr3/...`
passes.
