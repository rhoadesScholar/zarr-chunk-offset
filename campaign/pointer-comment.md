For anyone still watching this: a chunk-level version of what this issue asks for is now a
draft PR in the extension registry, zarr-developers/zarr-extensions#80: an `offset` chunk key
encoding (keys = `default` keys of `grid_coordinate + offset`), under which prepending `k`
whole chunks is two metadata edits and no chunk is renamed. Array indexing stays zero-based,
so it sidesteps the objections that closed #144. Implementations: a zarr-python plugin with
tests at https://github.com/rhoadesScholar/zarr-chunk-offset, and branches for zarr-python
core, tensorstore and neuroglancer linked from the PR. Feedback welcome there.
