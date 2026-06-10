"""Query endpoints: POST /api/query (the UI's run button) and
GET /api/query/export.csv (shareable CSV link, same encoded form as the
shareable URL)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.api.auth import require_skills
from app.api.cache import LRU
from app.config import get_settings
from app.observability.logging import log
from app.queries.aggregate import QueryResponse, run_query
from app.queries.csv_export import query_response_to_csv
from app.queries.encode import QueryDecodeError, canonical_hash, decode_query
from app.queries.tree import (
    AnyQueryNode,
    QueryNode,
    QueryValidationError,
    validate_limits,
    validate_refs,
)
from app.snapshot.models import Snapshot
from app.snapshot.store import get_snapshot_store

router = APIRouter(dependencies=[Depends(require_skills)])

_query_cache: LRU[QueryResponse] | None = None


def _get_query_cache() -> LRU[QueryResponse]:
    global _query_cache
    if _query_cache is None:
        _query_cache = LRU(max_size=get_settings().query_cache_size)
    return _query_cache


def reset_query_cache_for_tests() -> None:
    global _query_cache
    _query_cache = None


async def get_snapshot_or_503() -> Snapshot:
    """Current snapshot, or 503 while the upstream data is unavailable
    (cold start with the upstream down)."""
    store = get_snapshot_store(get_settings())
    try:
        return await store.get()
    except Exception as exc:
        log.warning("query.snapshot_unavailable", error=str(exc))
        raise HTTPException(status_code=503, detail="snapshot_unavailable") from exc


class QueryRequest(BaseModel):
    query: QueryNode
    # Zero-match users are appended after the matching rows when set.
    include_non_matching: bool = False


def _execute(snapshot: Snapshot, root: AnyQueryNode, include_non_matching: bool) -> QueryResponse:
    try:
        validate_limits(root)
        validate_refs(root, snapshot)
    except QueryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cache = _get_query_cache()
    key = f"{canonical_hash(root)}:{snapshot.version}:{include_non_matching}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = run_query(snapshot, root, include_non_matching=include_non_matching)
    cache.put(key, result)
    return result


@router.post("/api/query")
async def query(body: QueryRequest) -> QueryResponse:
    snapshot = await get_snapshot_or_503()
    return _execute(snapshot, body.query, body.include_non_matching)


@router.get("/api/query/export.csv")
async def export_csv(q: str, include_non_matching: bool = False) -> Response:
    try:
        root = decode_query(q)
    except QueryDecodeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    snapshot = await get_snapshot_or_503()
    result = _execute(snapshot, root, include_non_matching)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=query_response_to_csv(result),
        media_type="text/csv; charset=utf-8",
        headers={
            "content-disposition": f'attachment; filename="skillquery-{stamp}.csv"'
        },
    )
