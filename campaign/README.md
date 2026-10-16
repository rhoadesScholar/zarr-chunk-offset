# The offset chunk key encoding campaign

Opened as drafts on 2026-10-15; marked ready for review and announced on 2026-10-16 (cc d-v-b,
jbms, clbarnes on #80; d-v-b on #4516; jbms on #296 and #1133), and the pointer comment was posted
on zarr-specs #9 and #122. Each file here is the source of one PR body.

**2026-10-16, redirected and reworked.** jbms and d-v-b preferred an `origin` on the chunk grid
plus array bounds ([zarr-extensions#79](https://github.com/zarr-developers/zarr-extensions/issues/79)).
The four branches now implement the registry option from #79, a `regular_bounded` chunk grid with
`origin` and `lower_bound`; the registry entry moves from #80 (closed) to a new PR. The PR bodies
in this directory describe the superseded `offset` design and are kept as history.

| order | repo | branch | PR | body |
|---|---|---|---|---|
| 1 | zarr-developers/zarr-extensions | `chunk-key-encodings/offset` | [#80](https://github.com/zarr-developers/zarr-extensions/pull/80) | [zarr-extensions.md](zarr-extensions.md) |
| 2 | zarr-developers/zarr-python | `offset-chunk-key-encoding` | [#4516](https://github.com/zarr-developers/zarr-python/pull/4516) | [zarr-python.md](zarr-python.md) |
| 3 | google/tensorstore | `zarr3-offset-chunk-key-encoding` | [#296](https://github.com/google/tensorstore/pull/296) | [tensorstore.md](tensorstore.md) |
| 4 | google/neuroglancer | `zarr-offset-chunk-key-encoding` | [#1133](https://github.com/google/neuroglancer/pull/1133) | [neuroglancer.md](neuroglancer.md) |
| — | zarr-specs #9 and #122 | — | posted 2026-10-16 | [pointer-comment.md](pointer-comment.md) |


