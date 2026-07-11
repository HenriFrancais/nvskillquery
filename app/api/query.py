"""Query endpoints: POST /api/query (the UI's run button) and
GET /api/query/export.csv (shareable CSV link, same encoded form as the
shareable URL)."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.auth import access_scope
from app.api.cache import LRU
from app.config import get_settings
from app.observability.logging import log
from app.queries.aggregate import QueryResponse, run_query
from app.queries.csv_export import query_response_to_csv
from app.queries.doctrine import (
    DoctrineError,
    DoctrineLabel,
    DoctrineRef,
    DoctrineRefDecodeError,
    decode_doctrine_ref,
    expand_fit,
    find_fit,
)
from app.queries.encode import QueryDecodeError, canonical_hash, decode_query
from app.queries.tree import (
    AnyQueryNode,
    QueryNode,
    QueryValidationError,
    validate_groups,
    validate_limits,
    validate_refs,
)
from app.snapshot.models import Snapshot
from app.snapshot.store import get_snapshot_store

router = APIRouter()

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
    # Exactly one of `query` (manual builder) or `doctrine` (a fit + tier the
    # backend expands) must be present.
    query: QueryNode | None = None
    doctrine: DoctrineRef | None = None
    # Pool filter: only characters in these groups are considered. Empty = all.
    groups: list[str] = []
    # Zero-match users are appended after the matching rows when set.
    include_non_matching: bool = False


def _resolve_doctrine(snapshot: Snapshot, ref: DoctrineRef) -> tuple[AnyQueryNode, DoctrineLabel]:
    """Expand a doctrine ref into a runnable query + a provenance label."""
    fit = find_fit(snapshot, ref)
    if fit is None:
        identity = f"{ref.doctrine}/{ref.role}/{ref.ship_type}/{ref.fit_name}"
        raise HTTPException(status_code=422, detail=f"unknown doctrine fit: {identity}")
    try:
        root = expand_fit(fit, ref.tier)
    except DoctrineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    label = DoctrineLabel(**ref.model_dump(), skill_count=len(root.children))
    return root, label


def _execute(
    snapshot: Snapshot,
    root: AnyQueryNode,
    groups: list[str],
    include_non_matching: bool,
    restrict_to_user_id: int | None,
) -> QueryResponse:
    try:
        validate_limits(root)
        validate_refs(root, snapshot)
        validate_groups(groups, snapshot)
    except QueryValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cache = _get_query_cache()
    # restrict_to_user_id MUST be part of the key: a self-scoped member and a
    # full-visibility caller run identical query trees but must never share a
    # cached result (that would leak the whole corp to a scoped member).
    key = (
        f"{canonical_hash(root)}:{','.join(sorted(groups))}"
        f":{snapshot.version}:{include_non_matching}:{restrict_to_user_id}"
    )
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = run_query(
        snapshot,
        root,
        groups=groups,
        include_non_matching=include_non_matching,
        restrict_to_user_id=restrict_to_user_id,
    )
    cache.put(key, result)
    return result


def _resolve_scope(request: Request, snapshot: Snapshot) -> int | None:
    """The user_id to restrict results to (None = full corp visibility).
    Rejects callers with no roster match — the same gate `require_access`
    applies to the other routers."""
    scope = access_scope(request, snapshot)
    if scope is None:
        raise HTTPException(status_code=403, detail="forbidden")
    return None if scope == "all" else scope


@router.post("/api/query")
async def query(body: QueryRequest, request: Request) -> QueryResponse:
    if (body.query is None) == (body.doctrine is None):
        raise HTTPException(
            status_code=422, detail="provide exactly one of query or doctrine"
        )
    snapshot = await get_snapshot_or_503()
    restrict = _resolve_scope(request, snapshot)
    if body.doctrine is not None:
        root, label = _resolve_doctrine(snapshot, body.doctrine)
        result = _execute(
            snapshot, root, body.groups, body.include_non_matching, restrict
        )
        # model_copy so the shared (provenance-free) cache entry isn't mutated.
        return result.model_copy(update={"doctrine": label})
    assert body.query is not None  # guarded above
    return _execute(
        snapshot, body.query, body.groups, body.include_non_matching, restrict
    )


@router.get("/api/query/export.csv")
async def export_csv(
    request: Request,
    q: str | None = None,
    d: str | None = None,
    g: str = "",
    include_non_matching: bool = False,
) -> Response:
    """Same encoded forms as the shareable URL: `q=` for a manual query tree,
    `d=` for a doctrine ref. Exactly one is required."""
    if (q is None) == (d is None):
        raise HTTPException(status_code=422, detail="provide exactly one of q or d")
    snapshot = await get_snapshot_or_503()
    restrict = _resolve_scope(request, snapshot)
    label: DoctrineLabel | None = None
    if d is not None:
        try:
            ref = decode_doctrine_ref(d)
        except DoctrineRefDecodeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        root, label = _resolve_doctrine(snapshot, ref)
    else:
        assert q is not None  # guarded above
        try:
            root = decode_query(q)
        except QueryDecodeError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    groups = [s for s in g.split(",") if s]
    result = _execute(snapshot, root, groups, include_non_matching, restrict)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%d-%H%M%S")
    return Response(
        content=query_response_to_csv(result, doctrine=label),
        media_type="text/csv; charset=utf-8",
        headers={
            "content-disposition": f'attachment; filename="skillquery-{stamp}.csv"'
        },
    )
