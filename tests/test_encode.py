"""base64url query encoding: round-trips, canonical hashing, garbage input."""

from __future__ import annotations

import pytest

from app.queries.encode import QueryDecodeError, canonical_hash, decode_query, encode_query
from app.queries.tree import QUERY_NODE_ADAPTER


def q(data: dict) -> object:
    return QUERY_NODE_ADAPTER.validate_python(data)


TREE = {
    "kind": "group", "op": "or", "children": [
        {"kind": "group", "op": "and", "children": [
            {"kind": "skill", "skill_id": 1000, "min_level": 4},
            {"kind": "skill", "skill_id": 1001, "min_level": 3},
        ]},
        {"kind": "skill", "skill_id": 1002, "min_level": 5},
    ],
}


def test_round_trip():
    node = q(TREE)
    assert decode_query(encode_query(node)) == node


def test_encoding_is_padding_free_and_url_safe():
    encoded = encode_query(q(TREE))
    assert "=" not in encoded
    assert "+" not in encoded
    assert "/" not in encoded


@pytest.mark.parametrize("garbage", ["", "!!!not-base64!!!", "aGVsbG8", "eyJrIjogMX0"])
def test_garbage_input_raises_decode_error(garbage: str):
    # "aGVsbG8" is valid base64 for "hello" (not JSON); "eyJrIjogMX0" is valid
    # JSON but not a query tree.
    with pytest.raises(QueryDecodeError):
        decode_query(garbage)


def test_legacy_char_type_tree_rejected():
    # Encoded pre-redesign URLs carrying char_type conditions must not decode.
    import base64
    import json

    legacy = {"kind": "char_type", "char_type": "Dreadnought"}
    encoded = base64.urlsafe_b64encode(json.dumps(legacy).encode()).decode().rstrip("=")
    with pytest.raises(QueryDecodeError):
        decode_query(encoded)


def test_canonical_hash_stable_and_discriminating():
    a = q(TREE)
    b = q(TREE)
    assert canonical_hash(a) == canonical_hash(b)
    different = q({**TREE, "op": "and"})
    assert canonical_hash(a) != canonical_hash(different)
