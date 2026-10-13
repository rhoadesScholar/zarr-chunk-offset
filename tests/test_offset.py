import json

import numpy as np
import pytest
import zarr
from zarr.core.chunk_key_encodings import DefaultChunkKeyEncoding, parse_chunk_key_encoding

from zarr_chunk_offset import NAME, OffsetChunkKeyEncoding, adopt, prepend_chunks


def _keys(store):
    from zarr.core.sync import sync

    async def _list():
        return [k async for k in store.list()]

    return sorted(sync(_list()))


def test_zero_offset_is_the_default_encoding_byte_for_byte():
    for sep in ("/", "."):
        default = DefaultChunkKeyEncoding(separator=sep)
        offset = OffsetChunkKeyEncoding(separator=sep, offset=(0, 0, 0))
        for coords in [(0, 0, 0), (3, 1, 7), (12, 0, 5)]:
            assert offset.encode_chunk_key(coords) == default.encode_chunk_key(coords)
    assert OffsetChunkKeyEncoding().encode_chunk_key((2, 3)) == "c/2/3"


def test_offset_shifts_keys_and_round_trips_including_negative_keys():
    enc = OffsetChunkKeyEncoding(offset=(-2, 1))
    assert enc.encode_chunk_key((0, 0)) == "c/-2/1"
    assert enc.encode_chunk_key((5, 4)) == "c/3/5"
    for coords in [(0, 0), (5, 4), (7, 0)]:
        assert enc.decode_chunk_key(enc.encode_chunk_key(coords)) == coords
    with pytest.raises(ValueError, match="dimensions"):
        enc.encode_chunk_key((1, 2, 3))


def test_metadata_round_trips_through_zarr_json_and_the_registry():
    d = OffsetChunkKeyEncoding(offset=(-1, 0)).to_dict()
    assert d == {"name": NAME, "configuration": {"separator": "/", "offset": [-1, 0]}}
    assert parse_chunk_key_encoding(json.loads(json.dumps(d))) == OffsetChunkKeyEncoding(offset=(-1, 0))


def test_the_entry_point_is_declared():
    from importlib.metadata import entry_points

    names = {e.name: e.value for e in entry_points(group="zarr.chunk_key_encoding")}
    assert names.get(NAME) == "zarr_chunk_offset:OffsetChunkKeyEncoding"


def test_adopt_then_prepend_is_metadata_only(tmp_path):
    rng = np.random.default_rng(0)
    data = rng.integers(0, 255, size=(8, 6), dtype=np.uint8)
    a = zarr.create_array(store=str(tmp_path / "a.zarr"), shape=(8, 6), chunks=(2, 3),
                          dtype="uint8", fill_value=0)
    a[:] = data
    before = _keys(a.store)
    assert "c/0/0" in before and "c/3/1" in before

    a = adopt(a)
    assert _keys(a.store) == before
    np.testing.assert_array_equal(a[:], data)
    assert json.loads((tmp_path / "a.zarr" / "zarr.json").read_text())["chunk_key_encoding"] == {
        "name": NAME, "configuration": {"separator": "/", "offset": [0, 0]}}

    a = prepend_chunks(a, axis=0, n=2)
    assert a.shape == (12, 6)
    assert _keys(a.store) == before
    np.testing.assert_array_equal(a[4:], data)
    np.testing.assert_array_equal(a[:4], 0)

    a[:4] = 7
    np.testing.assert_array_equal(a[:4], 7)
    np.testing.assert_array_equal(a[4:], data)
    after = _keys(a.store)
    assert set(before) < set(after)
    assert {"c/-2/0", "c/-2/1", "c/-1/0", "c/-1/1"} <= set(after)

    reopened = zarr.open_array(store=str(tmp_path / "a.zarr"), mode="r")
    assert reopened.shape == (12, 6)
    np.testing.assert_array_equal(reopened[:], a[:])


def test_prepend_refuses_a_default_encoded_array_and_a_bad_axis(tmp_path):
    a = zarr.create_array(store=str(tmp_path / "b.zarr"), shape=(4, 4), chunks=(2, 2),
                          dtype="uint8")
    with pytest.raises(ValueError, match="adopt"):
        prepend_chunks(a, axis=0, n=1)
    a = adopt(a)
    with pytest.raises(ValueError, match="out of range"):
        prepend_chunks(a, axis=2, n=1)
    with pytest.raises(ValueError, match=">= 0"):
        prepend_chunks(a, axis=0, n=-1)


def test_a_group_member_and_a_dot_separator_work(tmp_path):
    g = zarr.open_group(store=str(tmp_path / "g.zarr"), mode="w")
    a = g.create_array("s0", shape=(4,), chunks=(2,), dtype="int16",
                       chunk_key_encoding={"name": "default", "separator": "."})
    a[:] = np.arange(4, dtype=np.int16)
    a = adopt(a)
    a = prepend_chunks(a, axis=0, n=1)
    assert a.shape == (6,)
    np.testing.assert_array_equal(a[2:], np.arange(4))
    a[:2] = -1
    assert "s0/c.-1" in _keys(a.store)
    np.testing.assert_array_equal(zarr.open_array(store=str(tmp_path / "g.zarr"), path="s0",
                                                  mode="r")[:], [-1, -1, 0, 1, 2, 3])
