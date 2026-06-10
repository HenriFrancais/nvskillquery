"""Shareable-URL encoding of query trees: padding-free base64url JSON.

Mirrored by frontend/src/query/encode.ts — keep the two in sync. The
canonical hash keys the query-result LRU together with the snapshot version.
"""

from __future__ import annotations

import base64
import binascii
import hashlib

from pydantic import ValidationError

from app.queries.tree import QUERY_NODE_ADAPTER, AnyQueryNode


class QueryDecodeError(ValueError):
    """The q= parameter is not a valid encoded query tree."""


def encode_query(root: AnyQueryNode) -> str:
    raw = QUERY_NODE_ADAPTER.dump_json(root)
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_query(q: str) -> AnyQueryNode:
    padded = q + "=" * (-len(q) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise QueryDecodeError("not valid base64url") from exc
    try:
        return QUERY_NODE_ADAPTER.validate_json(raw)
    except ValidationError as exc:
        raise QueryDecodeError(f"not a valid query tree: {exc}") from exc


def canonical_hash(root: AnyQueryNode) -> str:
    # model field order is declaration order, so dump_json is deterministic
    # for equal trees.
    return hashlib.sha256(QUERY_NODE_ADAPTER.dump_json(root)).hexdigest()
