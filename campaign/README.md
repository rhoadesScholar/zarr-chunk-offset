# The offset chunk key encoding campaign

Nothing here has been posted. Each file is the body of one PR, ready to paste, in the order
they should go out. Branches live on forks under `rhoadesScholar`; no upstream PR exists yet.

| order | repo | branch | PR body |
|---|---|---|---|
| 1 | zarr-developers/zarr-extensions | `chunk-key-encodings/offset` | [zarr-extensions.md](zarr-extensions.md) |
| 2 | zarr-developers/zarr-python | `offset-chunk-key-encoding` | [zarr-python.md](zarr-python.md) |
| 3 | google/tensorstore | `zarr3-offset-chunk-key-encoding` | [tensorstore.md](tensorstore.md) |
| 4 | google/neuroglancer | `zarr-offset-chunk-key-encoding` | [neuroglancer.md](neuroglancer.md) |
| — | zarr-specs #9 and #122 | — | [pointer-comment.md](pointer-comment.md) |

Before posting anything:

1. `gh repo edit rhoadesScholar/zarr-chunk-offset --visibility public` (the registry README and
   every PR body link here; the registry's link checker fails on a private repo).
2. Open the zarr-extensions PR as a draft; the spec asks for registration before any
   implementation ships, so the three reader PRs reference it by number once it exists.
3. The zarr-python changelog fragment is `changes/+offset-chunk-key-encoding.feature.md`;
   rename it to `<PR number>.feature.md` once the PR number is known.
4. Fill in `<N>` placeholders.
