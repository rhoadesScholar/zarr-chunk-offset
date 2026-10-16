# What a negative-direction growth costs

`prepend_cost.py` grows a Zarr v3 array by two chunk rows in front of axis 0 and times the
only ways to do that today against the metadata edit that `regular_bounded` makes possible. Every
chunk is 64³ uint8 (262 144 bytes, uncompressed); the array is `(n0, 8, 8)` chunks.

Methods that exist today (array on the `regular` grid; every chunk changes key):

* `rename`: `resize`, then one `os.rename` per chunk file, highest index first. Filesystem
  stores only, and the best case there: one syscall per chunk, no bytes copied.
* `set-del`: `resize`, then `store.get` + `store.set` under the new key + `store.delete` for
  every chunk through the zarr store API. What an object store makes you do (copy + delete).
* `copy`: a new array of the grown shape, the data copied across. What most code does.

After (`bounded`): one `zarr.json` write that switches the grid to `regular_bounded` and lowers
`lower_bound`, which is the metadata step of `Array.prepend`. No chunk is read, moved or rewritten.
Writing the new data costs the same in every method and is not timed.

## granule (AMD EPYC 9454, NVMe, zarr-python 3.4.1, numpy 2.5.4)

`python bench/prepend_cost.py --chunks 64 512 4096 32768 --k 2`; wall seconds, one run each.
The first three columns are from 2026-10-15, the last from 2026-10-16.

| store  | chunks | rename | set-del | copy    | **bounded** | keys touched (before / after) |
|--------|-------:|-------:|--------:|--------:|------------:|------------------------------|
| memory |     64 |      – |  0.0075 |  0.0232 | **0.0002** | 64 / 0 |
| memory |    512 |      – |  0.0569 |  0.1264 | **0.0002** | 512 / 0 |
| memory |   4096 |      – |  0.8824 |  0.9838 | **0.0002** | 4096 / 0 |
| memory |  32768 |      – |  4.7831 |  7.6033 | **0.0002** | 32768 / 0 |
| local  |     64 | 0.0035 |  0.1094 |  0.0698 | **0.0008** | 64 / 0 |
| local  |    512 | 0.0295 |  0.7583 |  0.3202 | **0.0013** | 512 / 0 |
| local  |   4096 | 0.1289 |  5.9300 |  3.0802 | **0.0020** | 4096 / 0 |
| local  |  32768 | 1.0439 | 44.2483 | 26.4672 | **0.0018** | 32768 / 0 |

The "before" columns grow with the chunk count (and, on an object store, with the bytes: a copy
+ delete per chunk); the "after" column is one small file write whatever the array size. At
32 768 chunks (8 GiB) today's ways take 1 s to 44 s and the metadata edit about 2 ms.

Raw rows: `results-2026-10-15-granule.jsonl`, `results-2026-10-16-granule-regular-bounded.jsonl`.
An earlier run measured the superseded `offset` chunk key encoding (`--methods offset`).
