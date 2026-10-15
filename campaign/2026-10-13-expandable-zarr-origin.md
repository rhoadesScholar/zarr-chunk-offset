# Expandable zarr arrays: state of the art on a movable origin (2026-10-13)

Research question: can a zarr array's origin move so that data is PREPENDED (growth toward negative
indices) without rewriting or renaming chunks? Sources are primary (spec text, source code, issue
threads read via `gh`, rendered docs via WebFetch). Each claim is tagged **[verified]** (read in the
primary source) or **[inference]** (derived from what was read).

Read-only research: nothing was posted, commented or filed.

---

## 0. Bottom line

- **No zarr v3 spec text, registered extension, or shipped implementation lets the chunk grid's
  origin move.** [verified] The regular grid is anchored at array index 0 (§1.1); the extension
  registry holds `regular` and `rectilinear` grids and `default`, `v2`, `template` key encodings,
  none with an offset (§1.4); tensorstore documents "`ChunkLayout.grid_origin` is always the zero
  vector" (§3); neuroglancer reads only `chunk_shape` and `^(v2|default)$` (§4).
- **The idea has been proposed twice and never rejected on its merits.** [verified] zarr-specs #9
  (chairmank, 2018, open, `protocol-extension`) proposes exactly `chunk_origin` + negative chunk
  indices; #122 / PR #144 (jbms, 2021-2023) proposed a non-zero ARRAY origin and was closed when the
  non-zero-origin half was redirected to "an extension" — with rabernat, d-v-b and jstriebel each
  sketching the chunk-level variant (§1.3).
- **The chunk-level variant is implementable today in zarr-python as a plugin**, because
  zarr-python 3.1.3 added a chunk-key-encoding registry (PR #3436, merged 2025-09-17) and the
  registry process already accepted a third-party key encoding (`template`, PR #69) (§2, §1.4).
- **The one unsafe design is an extra key on the `regular` grid's configuration**: zarr-python
  and neuroglancer both read only `chunk_shape` and would open such an array and map every chunk
  to the wrong place with no error (§2.2, §4). The simplest SAFE proposal is a new chunk key
  encoding NAME that carries a per-dimension integer offset (§7).

---

## 1. zarr v3 specification

### 1.1 Regular chunk grid — anchored at array index 0

Source: https://zarr-specs.readthedocs.io/en/latest/v3/chunk-grids/regular-grid/index.html [verified]

- "An element of an array with coordinates (c, b, a, …) will occur within the chunk at grid index
  (c // dz, b // dy, a // dx, …)."
- The chunk at grid index (0, 0, 0, …) has its origin at (0, 0, 0, …); "the grid is aligned with the
  origin of the array." The page states that the case where grid and array are NOT aligned at the
  origin is not considered by this specification, and that "extensions may define variations on the
  regular grid type."
- "If the length of any array dimension is not perfectly divisible by the chunk length along the
  same dimension, then the grid will overhang the edge of the array space." Overhang is only on the
  far edge; "Chunks at the border of an array always have the full chunk size".
- Grid shape is "(ceil(z / dz), ceil(y / dy), ceil(x / dx), …)".

Core spec (https://zarr-specs.readthedocs.io/en/latest/v3/core/index.html, source
https://raw.githubusercontent.com/zarr-developers/zarr-specs/main/docs/v3/core/index.rst) [verified]:

- `chunk_grid` field: "The chunk grid of the Zarr array." `chunk_key_encoding` field: "The mapping
  from chunk grid cell coordinates to keys in the underlying store."
- Storage: "Let data_key(P, j, i ...) be the data key for P for the chunk with grid coordinates
  (j, i, ...)." — keys are a function of GRID coordinates, not array coordinates.
- Resizing: "In general, arrays can be resized for writable (and, if necessary, deletable)
  stores." / "For areas where no chunks existed previously, they implicitly have the fill value
  after updating the metadata." Nothing about origins or prepending.
- Chunk-grid extensions must define chunk identifiers that are "a string of ASCII characters that
  can be used to construct keys."

### 1.2 Chunk key encodings

`default` (https://zarr-specs.readthedocs.io/en/latest/v3/chunk-key-encodings/default/index.html) [verified]:
"The key for a chunk with grid index (k, j, i, …) is formed by taking the initial prefix c" then,
per dimension, "the separator character, followed by, the ASCII decimal string representation of
the chunk index within that dimension." Separator "/" or ".", default "/". Example `"c/1/23/45"`.
Zero-dimensional: key is `c`.

`v2` (https://zarr-specs.readthedocs.io/en/latest/v3/chunk-key-encodings/v2/index.html) [verified]:
"the ASCII decimal string representation of the chunk index within that dimension, followed by the
separator character, except that it is omitted for the last dimension." Default separator ".";
0-D key `"0"`.

Neither encoding defines the sign of a chunk index; both say "ASCII decimal string". Store keys:
"a key is a Unicode string, where the final character is not a / character." Node-name guidance
recommends `a-z, A-Z, 0-9, -, _, .` — so `-` is within the recommended set and nothing in the spec
forbids a key such as `c/-1/0`. [verified that no restriction exists in the text; that `c/-1/0`
is therefore legal is an inference]

### 1.3 Extension points and the `must_understand` rule

Core spec [verified]:
- Extension points: data type, chunk grid, chunk key encoding, codecs, storage transformer.
- "An implementation MUST fail to open Zarr groups or arrays if any metadata fields are present"
  that it does not recognise unless they opt out, and: "**must_understand=False is not supported for
  the following extension points: data type, chunk grid, and chunk key encoding.**" Consequently a
  new chunk-grid or chunk-key-encoding NAME must be rejected by any reader that lacks it — there is
  no silent-ignore path for a new name (there IS one for a new KEY inside an existing name's
  configuration; see §2.2, §4).
- Extension names must be registered "prior to release in any implementation within the
  zarr-extensions Github" repository (https://github.com/zarr-developers/zarr-extensions); URI names
  are now "discouraged for new extensions" but still permitted. "Registered names MUST start with
  one lower case letter a-z".

### 1.4 The extension registry (zarr-developers/zarr-extensions) [verified by directory + PR listing]

- README process: "open a new PR with a new extension directory under the relevant extension
  point"; "Each extension MUST have a README.md file that describes the extension"; a `schema.json`
  SHOULD accompany it; "The PR will be reviewed by the Zarr Format Working Group (ZFWG)" with review
  focused on "avoiding confusing extension names and preventing malicious activity"; "Extensions
  SHOULD have an implementation that proves the viability of the proposed extension"; licence CC BY
  3.0. **No ZEP is mentioned.**
- `chunk-grids/`: `regular` (README is one line: a link to the core spec), `rectilinear`
  (merged PR #25, d-v-b). `chunk-key-encodings/`: `default`, `v2`, `template` (merged PR #69,
  clbarnes; a format-string encoding whose expressions are only coordinate INDICES with optional
  zero-padding — it cannot add an offset to a coordinate value). Open CKE PRs: #28 `suffix`
  (mkitti, 2025-10-16), #31 `fanout` (remcofl, 2025-10-20, explicitly motivated by the zarr-python
  3.1.3 registry); #47 `prefix` (d-v-b) closed.
- **No extension, merged or pending, carries an origin, offset, or negative-index concept**
  (all 54 PRs in `gh pr list --state all --limit 200` read by title; the closest is #7 "Reserve
  characters in names", mkitti, open).

### 1.5 Threads about origin / negative chunks / prepending

**zarr-specs #9 "Negative chunk indexes, offset chunk origin"** — https://github.com/zarr-developers/zarr-specs/issues/9
[verified] Opened 2018-06-07 by **chairmank**; label `protocol-extension`; **OPEN**.
Proposal verbatim: "Overhanging chunks may appear along any edge of the array" and "The array
metadata has a new key, `chunk_origin` (feel free to invent a better name!), which specifies the
location in the N-dimensional array of the origin "corner" of the `[0, 0, ..., 0]`th chunk. If
unspecified, the default value of `chunk_origin` is `[0, 0, ..., 0]` … to preserve backwards
compatibility." and "Chunk indices may be negative". Worked example: prepend one row by setting
shape `[4,3]`, chunk origin `[1,0]`, adding chunks `[-1,0]`, `[-1,1]`; all existing chunks
unchanged.
Engagement: **alimanfoo** (2018-06-21: "a neat idea… as easy to append as to prepend"; suggests a
second item `array_origin` so growth need not be a chunk multiple; wants use cases and other
implementations consulted); **tam203** (Met Office, 2019-03-15: "I've implemented this spec change
(sort of)", blog + binder); alimanfoo (2019-03-15: "in scope for the next spec version", migrates
issue to zarr-specs); **meggart** (Zarr.jl/ESDL, 2019-03-18: "big +1", already stores an offset
attribute); **rsignell-usgs** (2019-06-28: US National Water Center interest); **bluppfisk**
(2023-01-19: +1, concern about chunk ids growing huge); **jbms** (2023-01-19, last comment):
"This is not planned to be part of the initial zarr v3 spec, but it would be great to standardize
this as an extension soon." Outcome: open, nothing filed since.

**zarr-specs #122 "Support for non-zero origin"** — https://github.com/zarr-developers/zarr-specs/issues/122
[verified] Opened 2021-12-10 by **jbms**; labels `core-protocol-v3.0`, `protocol-extension`; **OPEN**.
Proposes an `origin` field changing INDEXING (`arr[1,2,3]` reads the origin; `arr[0,0,0]` out of
bounds); argues "This is not something that can be reasonable supported as an extension via a
custom attribute, because … the indexing would behave differently" in unaware readers. Explicitly
cites that it "makes it very easy to extend data in the negative direction".
Engagement: supporters **fcollman** (Allen Institute: alignment outputs land at non-zero or
negative voxels), **stuarteberg** (Janelia), **william-silversmith** (CloudVolume/precomputed
experience). Opposed to changing core indexing: **rabernat** ("Zarr's current indexing is …
strictly logical. I would be wary about bringing any domain-specific notions of coordinate systems
into Zarr itself"; points to xarray flexible indexes), **d-v-b** ("this is what xarray and other
libraries that wrap zarr are for"), **constantinpape** (prefers OME-NGFF translation; warn in
zarr-python), **jakirkham** (generalise to transforms?), **DennisHeimbigner** (netCDF coordinate
variables; confirms storage layout unaffected), **joshmoore** (call summary: "unclear if it belongs
in the core .zarray metadata or as a higher-level convention"). Outcome: open; superseded in
practice by PR #144's closure.

**zarr-specs PR #144 "Revise how the domain of an array is specified"** — https://github.com/zarr-developers/zarr-specs/pull/144
[verified] jbms, opened 2022-05-31, **CLOSED (not merged) 2023-01-20**. Added dimension names and
non-zero origins (`inclusive_min`/`exclusive_max` + `grid_origin`). Key exchanges:
- **meggart** (2022-06-08) and **rabernat** (2022-06-08) opposed offset indexing in core.
- jbms (2022-06-10) on mechanism: "the relevant offset (x, y, z) is the `grid_origin`, not the
  `inclusive_min` value for each dimension. The `inclusive_min` is only used for bounds checking,
  and does not affect how the data is retrieved."
- jbms (2022-06-16): "I can see that there is a strong opposition to non-zero origins in zarr, so I
  won't continue pushing it. … The one aspect of this proposal that is not as conveniently
  implemented outside of the core spec is support for growing a dimension in the negative
  direction".
- **rabernat** (2022-06-22): "I do agree that it would be great to allow extending arrays in both
  directions. I think that can be done without introducing coordinates. Maybe we could support this
  via an optional extension that would operate at the chunk level, i.e. creating chunks like
  `-1.0.0`."
- **d-v-b** (2022-06-22/23): "Why can't zarr just copy the numpy pad API?" and "you could allow
  chunks with negative integers in their names … but the first chunk is always addressed by
  `array[0, 0, ...]`. However … this would require explicitly tracking the name of the first chunk
  in some metadata." **joshmoore**: a pad that renames "would require moving every chunk file, no?
  And on s3 that would be a copy+delete."
- jbms (2022-06-23): "if `grid_origin` is supported (but the lower bound is still always 0) then it
  would indeed be possible to support an API like `pad`."
- **jstriebel** (2022-10-20 summary, with normanrz): point 3 "An indexing offset could change how
  data is stored in comparison how it is indexed … When only allowing chunk-wise offsets (so offset
  must be divisible by the chunk-size), this could be handled by a storage transformer." Point 5:
  left-padding "without renaming all written chunks" is the wanted property.
- Closing (jstriebel, 2023-01-20): dimension names went to PR #162; "non-zero origins (#122) is
  proposed as an extension, not being part of v3 core".

**Related, lighter threads** [verified]:
- zarr-specs #39 "Proposal: open ended zarrs" (jacobtomlinson, Met Office, 2018-11-05, open,
  `protocol-extension`): rolling datasets that remove old data "from the beginning of the array"
  would "require re-indexing all chunks"; 21 comments (alimanfoo, jakirkham, jhamman, jstriebel,
  tam203); last activity 2022-11-16 cross-referencing #138/#46.
- zarr-specs #212 (jbms, 2023-02-22, open, `core-protocol-v3.1`, 0 comments): per-dimension
  resizable flag; notes "with a non-zero origin we may wish to separately indicate whether the
  lower and upper bounds along a given dimension are resizable."
- Community call 2022-02-09 (https://zarr.dev/community-calls/2022/2022-02-09.html): JMS "benefit
  of allowing indexing to be affected"; DB "see the utility (working with cutouts) but the workflow
  puts us outside what's in the core spec"; EP "like the functionality, but it can be at a
  different level."
- Community call 2022-06-15 (https://zarr.dev/community-calls/2022/2022-06-15.html): RA "Zarr
  can't make Julia use index base"; DH "index level needs to be pure and standardised"; JK on
  negative indexing "to update the metadata for all the previous arrays"; MD "the reference file
  systems could do the renaming - but it is complicated".
- org discussion #52 (ZEP0003 variable chunks): jleben, 2025-11-02: "Currently, the python API
  only allows appending to an array, not prepending or inserting, presumably because the latter two
  would potentially require rechunking everything after the inserted part."

### 1.6 ZEP process (https://zarr.dev/zeps/active/ZEP0000.html) [verified]

- Types: Specification ("Currently, Specification ZEPs only deal with the core specification of
  Zarr"), Informational, Process. Workflow: vetting → draft PR (`zep-<n>.md`; a spec ZEP needs a
  second PR to zarr-specs) → discussion thread → Draft/Accepted/Rejected/Withdrawn/Deferred/
  Superseded/Provisional → Final.
- Core ZEPs need "Unanimous approval of the Zarr Steering Council", "Majority approval of the Zarr
  Implementations Council", and no veto ("Each implementation has the right to veto a ZEP if it
  would cause severe problems for that implementation"). Other ZEPs: "Proposal to accept" issue,
  "If there are no substantive objections within 7 days from this post, then the ZEP will be
  accepted."
- Index (https://zarr.dev/zeps/): Accepted ZEP0001, ZEP0002; Active ZEP0000, ZEP0011; Draft
  ZEP0003, 0004, 0005, 0009. The index says nothing about extensions; the zarr-extensions README
  (§1.4) is the operative process for a new chunk grid / key encoding and does not require a ZEP.
  [inference from the two documents together: an extension goes to zarr-extensions; a ZEP is for
  changing the core document.]

---

## 2. zarr-python 3.x

### 2.1 Registries [verified: src/zarr/registry.py]

`register_codec(key, codec_cls)`, `register_pipeline`, `register_buffer`, `register_ndbuffer`, and
**`register_chunk_key_encoding(key: str, cls: type)`**. Entry-point groups: `zarr.codecs` (and
`zarr.codecs.<name>`), `zarr.buffer`, `zarr.ndbuffer`, `zarr.data_type`,
**`zarr.chunk_key_encoding`**, `zarr.codec_pipeline`, plus the umbrella `zarr` group with
`name` ∈ {buffer, ndbuffer, data_type, chunk_key_encoding, codec_pipeline}. **There is no chunk-grid
registry**; the extending guide says "In the future, Zarr will support writing custom chunk grids."
The CKE registry landed in PR #3436 (remcofl, merged 2025-09-17, "Add registry for chunk key
encodings for extensibility", following #3433 by d-v-b).

`ChunkKeyEncoding` base (src/zarr/core/chunk_key_encodings.py): docstring "Defines how chunk
coordinates are mapped to store keys."; abstract `encode_chunk_key(self, chunk_coords: tuple[int,
...]) -> str`; optional `decode_chunk_key`. `parse_chunk_key_encoding` does
`get_chunk_key_encoding_class(name_parsed).from_dict(data)` and re-raises an unknown name as
`ValueError(f"Unknown chunk key encoding: {e.args[0]!r}")`. Base `from_dict` is
`cls(**config_parsed or {})`, so an unexpected configuration key is a dataclass `TypeError`.

### 2.2 Chunk grid parsing — an extra key is SILENTLY ignored [verified: src/zarr/core/metadata/v3.py]

```python
def from_dict(cls, data):
    parse_named_configuration(data, "regular")  # validate name
    configuration = data["configuration"]
    return cls(chunk_shape=parse_chunk_shape(configuration["chunk_shape"]))
```
`parse_chunk_grid` accepts `"regular"` and `"rectilinear"` (the latter behind the
`array.rectilinear_chunks` config flag, "experimental and disabled by default") and raises
`ValueError(f"Unknown chunk grid name: {name!r}")` otherwise. `parse_configuration` (common.py)
"only checks that the value is a dict and returns it unchanged". So `{"name":"regular",
"configuration":{"chunk_shape":[...],"origin":[...]}}` opens fine and ignores `origin`.
Unknown TOP-LEVEL fields are rejected unless `{"must_understand": false}`
(`MetadataValidationError`: "Extra fields are not allowed unless they are an object with a
"must_understand" key which is assigned the value `false`.").

### 2.3 Indexing and resize [verified]

- chunk_grids.py: `FixedDimension.index_to_chunk` returns `idx // self.size`; `all_chunk_coords`
  and `iter_chunk_regions` take an `origin` that defaults to `(0,) * self.ndim` — this is a
  selection origin in grid space, not a stored array origin. indexing.py subtracts
  `dim_offset = g.chunk_offset(dim_chunk_ix)` to get chunk-local positions; nothing subtracts a
  stored origin.
- User guide (https://zarr.readthedocs.io/en/stable/user-guide/arrays/): "Note that when an array
  is resized, the underlying data are not rearranged in any way." / "any chunks falling outside the
  new array shape will be deleted from the underlying store." `Array.append` "can be used to append
  data to any axis." **Prepending is not mentioned anywhere.** `AsyncArray.resize(…,
  delete_outside_chunks=True)`: "If True (default), chunks that fall outside the new shape will be
  deleted. If False, the data in those chunks will be preserved."
- Issue search (`prepend`, `non-zero origin`, `origin offset chunk grid`) in zarr-python finds no
  open issue on this topic [verified by `gh search issues`]; PR #4479 (d-v-b) makes a negative
  chunk index raise in `VaryingDimension.chunk_offset` [from search snippet, not read in full].

---

## 3. tensorstore

Zarr3 driver docs (https://google.github.io/tensorstore/driver/zarr3/index.html) [verified]:
- "**As Zarr v3 does not natively support a non-zero origin, the underlying domain always has a
  zero origin, but it may be translated by the transform.**"
- "**The ChunkLayout.grid_origin is always the zero vector.**"
- "The upper bounds of the domain are resizable" (implicit upper bounds only).
- `chunk_key_encoding`: "Specifies the encoding of chunk grid positions as keys in the underlying
  kvstore." Subtypes `default` (separator "/" or ".", default "/") and `v2` (default ".").
  Chunk grid: only `"regular"`.
- Source (tensorstore/driver/zarr3/metadata.cc): `jb::Member("name", jb::Constant([] { return
  "regular"; }))`; `chunk_key_encoding` kinds `{kDefault, "default"}, {kV2, "v2"}`;
  `SetChunkLayoutFromMetadata` sets `ChunkLayout::GridOrigin(GetConstantVector<Index, 0>(rank))`.
  Unknown top-level fields: `UnknownExtensionAttributesJsonBinder` accepts only
  `{"must_understand": false}` objects, else "Unsupported metadata field %v is not marked …".
- Index-space docs (https://google.github.io/tensorstore/index_space.html): a domain has
  `inclusive_min` per dimension; "Implicit bounds may be used for resizable dimensions of arrays."
  Spec docs: `transform` "Specifies a transform."; the schema `domain` "is always a hard constraint".

So: **a zarr3 TensorStore's stored domain is always zero-origin; a non-zero origin exists only in
the Spec's `transform` (an index transform in the JSON spec, not in `zarr.json`).** [verified]
Whether tensorstore would REJECT an unknown `origin` key inside `chunk_grid.configuration`:
json_binding.h says `jb::Object` "verifies that there are no remaining members" when loading, and
`DiscardExtraMembers` does not appear in metadata.cc — so it fails loudly. [inference from those
two readings; not executed]

No tensorstore issue about a zarr3 origin was found (`gh search issues --repo google/tensorstore
"origin zarr"` → only unrelated #40). [verified]

---

## 4. neuroglancer (src/datasource/zarr)

metadata/parse.ts [verified]:
- Chunk key encoding: `verifyEnumString(name, ChunkKeyEncoding, /^(v2|default)$/)`; separator
  via `parseDimensionSeparator` (`Expected "." or "/"`), default "/" for default, "." for v2.
- Chunk grid: `verifyConstant(name, "regular")`; configuration read only for `chunk_shape`
  (`Expected positive integer`). `parseNameAndConfiguration` (parse_util.ts) verifies `name` and
  that `configuration` is an object, then hands it to the callback; the callback reads only
  `chunk_shape`. **Unknown configuration keys are ignored; no `must_understand` check exists for
  unknown top-level fields** (parseV3Metadata reads only known fields). [the "ignored" conclusion
  is an inference from the code read; nothing in the file rejects extras]
- backend.ts key construction: for DEFAULT `baseKey += "c"`, then per dimension
  `keyCoords[decodedDim] = Math.floor((chunkGridPosition[fOrderPhysicalDim] *
  readChunkShape[decodedDim]) / chunkShape[decodedDim])` and `baseKey += \`${sep}${keyCoords[i]}\``.
  No offset anywhere.

ome.ts [verified]: accepts NGFF `"0.4"`, `"0.5-dev"`, `"0.5"`, `"0.6.dev1"`, `"0.6.dev3"`,
`"0.6"` (non-0.4/0.5-dev only with zarr v3). `scale` → homogeneous scale matrix; `translation` →
homogeneous translation matrix; list composed in order. Centre-vs-corner: "// In OME's coordinate
space, the origin of a voxel is its center, while in Neuroglancer it is the "lower" (in
coordinates) corner. Translate by the physical size of half a voxel" — applied as
`offset += t[j*(rank+1)+i] * 0.5; t[rank*(rank+1)+i] -= offset;`. **So neuroglancer honours
NGFF translation (as a centre) but has no concept of a chunk-grid origin.**

No neuroglancer issue about a zarr origin/offset was found. [verified by `gh search issues`]

---

## 5. OME-NGFF

0.4 (zarr v2, `.zarray`) and 0.5 (zarr v3, `zarr.json`; "use Zarr v3 in OME-Zarr, see RFC-2") carry
identical transformation rules (ome/ngff-spec `index.bs`, branches `0.4` and `0.5`) [verified]:
- "`coordinateTransformations` describe a series of transformations that map between two
  coordinate spaces (defined by "axes"). For example, to map a discrete data space of an array to
  the corresponding physical space." Types: `identity`, `translation` (`List[float]` or `path`),
  `scale`. "The transformations in the list are applied sequentially and in order."
- Per dataset: "Each dictionary in "datasets" MUST contain the field "coordinateTransformations"
  … The transformation MUST only be of type `translation` or `scale`. They MUST contain exactly one
  `scale` transformation … It MAY contain exactly one `translation` that specifies the offset from
  the origin in physical units. If `translation` is given it MUST be listed after `scale` to ensure
  that it is given in physical coordinates."
- Per multiscale: "MAY contain the field "coordinateTransformations" … applied after them."
- dev spec (0.9.dev2, https://ngff.openmicroscopy.org/specifications/dev/index.html): "**The
  pixel/voxel center is the origin of the continuous coordinate system.**"; 0.4 and 0.5 do not
  state it. (Matches the slabreg CLAUDE.md note.)
- Issues: ome/ngff #89 "Define the origin w.r.t. the pixel corner or center" (constantinpape,
  2022-02-01, OPEN, 30 comments; last, thewtex 2026-06-15: RFC-5 group "concluded that it will be
  included in OME-Zarr version 0.6"). ome/ngff #490 "explicitly define the original coordinate
  system of an array" (d-v-b, 2026-03-21, OPEN): "the array coordinate system is the set of array
  indices for the array, starting at (0, ...)"; mkitti replies that "In the frequency domain,
  negative indices are common." **NGFF translation is a continuous physical offset layered on a
  zero-based array; no NGFF issue proposes a zarr-level array origin** — #122 (constantinpape)
  records NGFF's position that this belongs in NGFF transforms, not zarr. [verified]

---

## 6. Prior art with a stored origin

| Format | Stored origin? | Evidence |
|---|---|---|
| **N5** | No | README mandatory dataset attributes are exactly `dimensions`, `blockSize`, `dataType`, `compression`; blocks at grid position `0/4/1/7`. [verified https://github.com/saalfeldlab/n5] |
| **neuroglancer precomputed** | **Yes** | `voxel_offset`: "must be a 3-element array [x, y, z] of integer values specifying a translation in voxels", default `[0,0,0]`; chunk names from `begin_offset = voxel_offset + g * chunk_size`, `end_offset = voxel_offset + min((g + 1) * chunk_size, size)`, file `<xBegin>-<xEnd>_<yBegin>-<yEnd>_<zBegin>-<zEnd>`. [verified src/datasource/precomputed/volume.md] Note the key embeds the OFFSET, so changing `voxel_offset` by a non-multiple of the chunk renames every chunk; by a chunk multiple it does not (grid index g shifts, names stay). [inference] jbms cites this in #122 as "proved to be quite useful". CloudVolume (william-silversmith) never added negative indices: "no one has ever asked me". |
| **HDF5** | No | A simple dataspace has rank, current dims and max dims ("The size of each dimension can grow … from the current size up to the maximum size", `H5S_UNLIMITED`); `H5Dset_extent` "sets the current dimensions of the chunked dataset dset_id to the sizes specified in size" — dims only, no lower bound; hyperslab `offset` is a selection. [verified HDF5 UG + H5D reference] |
| **xarray** | No | Positional indexing "works (mostly) just like it does for numpy arrays"; label-based `sel` looks positions up from coordinate values. Offsets are coordinate VARIABLES (rabernat/MD in #122 and the 2022-06-15 call: "each variable has unique set of coordinate - the NetCDF conventions would not allow it" negative-index remapping). [verified] |
| **Dask** | No stored origin; zero-based like numpy. [inference, not fetched] |
| **Kerchunk / VirtualiZarr** | Re-keying is a metadata edit | kerchunk refs map `"x/0": ["s3://…", 294094376, 73825960]` (url, byte offset, length) with "zero or more arbitrary keys" and Jinja generators. VirtualiZarr: a ChunkManifest is "a list of chunk keys and their corresponding byte ranges in specific files"; concatenation is done "via merging their chunk manifests into one" with "automatic re-labelling of their chunk keys". So a VIRTUAL array can be prepended by rewriting the manifest without touching bytes — but only because the manifest IS the key table; a materialised zarr store has no such indirection. [verified; the contrast is inference] |
| **Zarr.jl / ESDL** | User attribute | meggart in #9: "already using a user-space attribute specifying the array offset". [verified] |
| **Met Office rolling store** | Custom store wrapper | tam203 in #9: offset applied to chunk indexes, stored in `.zattrs` (Medium post is 403 today; `informatics-lab/rolling_zarr_array_store` 404s; the `mengjin001` fork, last pushed 2019-03-15, is the surviving copy). [verified status; mechanism from the #9 thread and search snippet] |

---

## 7. Simplest viable proposal

### 7.1 Rejected first: `origin` on the `regular` grid configuration

The obvious design — `{"name":"regular","configuration":{"chunk_shape":[…],"origin":[k,…]}}` —
is UNSAFE under the readers as they exist today: zarr-python (§2.2) and neuroglancer (§4) read only
`chunk_shape` and would open the array, address chunk `c/0/…` as array index 0 and show the wrong
data with no error. That is precisely the failure jbms warned of in #122 ("everything appears to
work except they will be using a different coordinate system"). tensorstore would likely refuse
(§3), which is the only acceptable behaviour. A new KEY inside an existing extension name has no
`must_understand` protection; only a new NAME does (§1.3). [verified rules + inferred consequence]

### 7.2 Proposed: an offset-carrying chunk key encoding under a NEW name

```json
"chunk_key_encoding": {
  "name": "offset",
  "configuration": { "separator": "/", "offset": [-3, 0, 0] }
}
```
Semantics: key = `default` key of `(grid_index + offset)` per dimension (optionally `"base":
"v2"` to use the v2 layout). `offset` defaults to all zeros, so `offset` with zeros is byte-for-byte
the `default` encoding. Array coordinates stay zero-based; `shape` keeps its meaning; the chunk grid
is untouched. Prepending `k` whole chunks on axis `a` is two metadata edits:
`shape[a] += k * chunk_shape[a]`, `offset[a] -= k`; existing chunks keep their keys (chunk formerly
at grid index g is now at g + k and its key is `g + k + (offset − k) = g + offset`). Negative keys
(`c/-1/0`) are legal store keys (§1.2) — a large positive bias is the alternative jbms named
("an initial origin that is some large number, e.g. 2^62") for stores that dislike `-`.
The mechanism is already shipped in one format: neuroglancer precomputed's `voxel_offset` enters
the chunk file name as `voxel_offset + g * chunk_size`, so moving it by a whole number of chunks
leaves every existing file name unchanged (§6). [inference from the verified naming formula]

Why this is the smallest change:
- Fails LOUDLY in every current reader: zarr-python "Unknown chunk key encoding: 'offset'",
  neuroglancer regex `^(v2|default)$`, tensorstore enum `{default, v2}`; and the spec forbids
  `must_understand=False` for this extension point. [verified]
- It is the design the objectors themselves proposed when #144 closed: rabernat's "optional
  extension that would operate at the chunk level, i.e. creating chunks like `-1.0.0`", d-v-b's
  "explicitly tracking the name of the first chunk in some metadata", jstriebel's "chunk-wise
  offsets… could be handled" outside core, jbms's own `grid_origin`-with-zero-lower-bound remark
  and his #9 close-out "standardize this as an extension soon". It sidesteps every #122 objection
  (indexing semantics, Julia index base, xarray coordinate model) because indexing is unchanged.
- zarr-python needs NO core change: `register_chunk_key_encoding` / entry point
  `zarr.chunk_key_encoding` exist since 3.1.3 (§2.1); a chunk-grid variant would instead wait on
  "In the future, Zarr will support writing custom chunk grids."
- The registry has precedent for exactly this kind of PR (`template` merged; `suffix`, `fanout`
  pending) with ZFWG review and no ZEP.

What it does NOT give: sub-chunk prepends (the first chunk would still have to be rewritten, which
alimanfoo's `array_origin` and jbms's `inclusive_min` addressed), and a user-facing non-zero ARRAY
origin (that stays in tensorstore `transform` / NGFF `translation`). Concurrency of the two
metadata edits is the writer's problem, as jbms noted ("This approach may raise some issues with
concurrent access").

### 7.3 Per-implementation changes to READ it

- **zarr-python**: a plugin package (`ChunkKeyEncoding` subclass with `name = "offset"`,
  `encode_chunk_key(chunk_coords)` adding the offset, `decode_chunk_key` subtracting it; registered
  via the `zarr.chunk_key_encoding` entry point). Optional later core PR: an `Array.prepend` /
  `pad` helper that performs the two metadata edits. [verified registry; helper is a proposal]
- **tensorstore**: a third `ChunkKeyEncoding::Kind` in metadata.cc with an `offset` member, and
  the offset added where grid cell indices are formatted into keys (the formatter lives outside
  metadata.cc; not located in this research). `ChunkLayout.grid_origin` and the zero-origin domain
  are unchanged; the "resize lower bound" operation would be a new op since today only upper bounds
  are implicit. [inference from §3]
- **neuroglancer**: extend the regex in parse.ts to `^(v2|default|offset)$`, parse `offset`, and
  add it in the backend.ts `keyCoords` loop. Read-only, so no prepend op needed. [inference from §4]
- **OME-NGFF / slabreg**: nothing changes in the OME metadata; `translation` keeps describing the
  physical position of array index 0. After a prepend of k chunks the array's index 0 moves, so the
  per-dataset `translation` must be decremented by `k * chunk * scale` to keep the physical frame
  — a second metadata edit the writer owns. For a multiscale group the prepend is metadata-only
  ONLY if it is a whole number of chunks at EVERY level: `k * chunk_s0 / downsample_i` must be a
  multiple of `chunk_si` for each `i`, which constrains the per-level chunk shapes at creation;
  otherwise the coarser levels are re-rendered — the s12 rebuild slabreg's CLAUDE.md already owes
  after every re-render, so a known cost rather than a new one. [inference]

### 7.4 Where to file

1. **zarr-extensions PR** (https://github.com/zarr-developers/zarr-extensions):
   `chunk-key-encodings/offset/README.md` + `schema.json`, reviewed by the ZFWG; no ZEP (§1.4).
   Ship the zarr-python plugin first to satisfy "Extensions SHOULD have an implementation". Open as
   a draft PR, link #9 and #122, and post a pointer in both.
2. A ZEP is only needed if the aim is to change the CORE document (e.g. make `regular` itself
   carry an origin) — that is a Core ZEP needing unanimous ZSC + majority ZIC approval (§1.6), the
   route #144 failed on.
3. Downstream: a tensorstore issue/PR and a neuroglancer PR once the name is registered (the spec
   requires registration "prior to release in any implementation").

### 7.5 Who has engaged (for cc / review)

Original proposers and allies: **chairmank** (#9), **jbms** (#122, #144, tensorstore +
neuroglancer author — the reviewer whose two implementations must change), **tam203** /
**jacobtomlinson** (Met Office, #9/#39), **meggart** (Zarr.jl), **rsignell-usgs**, **fcollman**
(Allen), **stuarteberg** (Janelia), **william-silversmith** (CloudVolume), **bluppfisk**.
Objectors to core indexing change who endorsed a chunk-level extension: **rabernat**, **d-v-b**
(now a zarr-extensions maintainer with many merged PRs there), **jstriebel**, **normanrz**,
**constantinpape**, **joshmoore**, **alimanfoo** (open to it in 2018-19), **jakirkham**,
**DennisHeimbigner** (netCDF). Registry-process people: **clbarnes** (`template`), **remcofl**
(`fanout`, wrote the zarr-python CKE registry), **mkitti** (`suffix`, ngff #490).

---

## 8. Verification ledger

Verified in primary sources: spec text (§1.1-1.3, 1.6), registry contents and full PR list
(§1.4), every issue/PR thread quoted (§1.5, read via `gh` with comment bodies), zarr-python
registry/metadata/indexing/user-guide (§2), tensorstore zarr3 docs + metadata.cc + index-space
docs (§3), neuroglancer parse.ts / parse_util.ts / backend.ts / ome.ts (§4), NGFF 0.4/0.5 `index.bs`
and dev spec sentence (§5), N5 README, precomputed volume.md, HDF5 UG/H5D, kerchunk spec,
VirtualiZarr data-structures page, xarray indexing page (§6).

Inferences: that `c/-1/0` is a legal key (no rule forbids it); that tensorstore rejects an unknown
`chunk_grid.configuration` member (from `jb::Object` docs + absence of `DiscardExtraMembers`); that
neuroglancer ignores one (from reading only `chunk_shape`); the per-implementation change lists in
§7.3; the NGFF-translation bookkeeping; Dask having no origin. Not reached: the Medium post (403),
the original Met Office repo (404), tensorstore's key-formatting source file, the tail of
zarr-python `array.py` beyond 100k characters.
