Title: zarr: read the offset chunk key encoding

Reads arrays that use the `offset` chunk key encoding
(zarr-developers/zarr-extensions#<N>): the `default` key of `grid coordinate + offset`, one
integer per dimension, any sign. Writers use it to grow an array in the negative direction by
whole chunks without renaming chunks (zarr-developers/zarr-python#<N>,
google/tensorstore#<N>).

**Before / after.** Before: the `chunk_key_encoding` name regex is `^(v2|default)$`, so such an
array fails to parse. After: `offset` parses (one integer per dimension, separator `/` by
default) and the chunk key adds the offset per dimension, so grid coordinate `(0, 0)` under
`offset [-2, 1]` is fetched from `c/-2/1`.

**Changes**

- `ChunkKeyEncoding.OFFSET`; `ArrayMetadata.chunkKeyOffset` (undefined for the other
  encodings, including v2 metadata).
- The key string composition moves out of `ZarrVolumeChunkSource.download` into
  `encodeChunkKey(metadata, keyCoords)` in `metadata/index.ts`, so it can be unit-tested;
  behaviour for `default` and `v2` is unchanged. Sharding is unaffected: only the outer key
  changes.
- `offset.spec.ts`: parsing (defaults, explicit separator, missing / wrong-length /
  non-integer offset, other encodings unaffected) and key formatting (default and v2 as before,
  negative components, zero offset equals default).

- `testdata/datasource/zarr/zarr_v3/examples/offset_grown`: a `(6, 7)` uint16 array written
  under `default`, then grown by one chunk row in front through the metadata edit (shape
  `(10, 7)`, `offset [-1, 0]`, keys `c/-1/*` beside the untouched `c/0/*`, `c/1/*`), added to
  `tests/datasource/zarr.browser_test.ts` with its metadata snapshot.

Verified: `vitest` for the new spec and for `src/datasource/zarr`, the browser metadata
snapshot tests (headless Chromium), `tsc --noEmit`, oxlint, eslint, prettier. Not verified
here: rendering such a store interactively.
