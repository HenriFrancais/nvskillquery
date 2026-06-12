"""Run a query tree over a snapshot and aggregate matches per user.

The response models live here (not in the API layer) so the whole
query pipeline — tree → evaluate → aggregate — is pure and testable
without HTTP.

The ``groups`` pool filter scopes which characters exist as far as the
query is concerned: only pool members are evaluated, listed, or counted.
The main character is the one exception — it is always displayed for
identification, but can only be flagged as matching when it is in the pool.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from pydantic import BaseModel

from app.queries.doctrine import DoctrineLabel
from app.queries.evaluate import character_matches
from app.queries.sp_cost import character_gap
from app.queries.tree import AnyQueryNode
from app.snapshot.models import Snapshot


class CharacterOut(BaseModel):
    character_id: int
    name: str
    group: str


class MainCharacterOut(CharacterOut):
    matches: bool


class UserRow(BaseModel):
    user_id: int
    user_name: str
    main_character: MainCharacterOut
    matching_characters: list[CharacterOut]
    match_count: int
    total_characters: int  # pool members only


class QueryTotals(BaseModel):
    users_with_matches: int
    total_matching_characters: int
    total_users: int  # users with at least one pool character
    total_characters: int  # pool size


class QueryResponse(BaseModel):
    rows: list[UserRow]
    totals: QueryTotals
    snapshot_version: int
    snapshot_fetched_at: str  # ISO 8601
    # Minimal additional SP for each non-matching pool character to satisfy the
    # query — one entry per non-matching character, unordered. Powers the
    # distance-to-target chart. Independent of include_non_matching (which only
    # governs which user rows are returned).
    additional_sp: list[int] = []
    # Set only for doctrine-sourced queries — names the fit + tier behind the
    # expanded skill set. None for manual queries. Attached after aggregation
    # (the cached result is provenance-free and shared with the manual path).
    doctrine: DoctrineLabel | None = None


def run_query(
    snapshot: Snapshot,
    root: AnyQueryNode,
    groups: Sequence[str] = (),
    include_non_matching: bool = False,
) -> QueryResponse:
    pool = set(groups)
    matching_rows: list[UserRow] = []
    empty_rows: list[UserRow] = []
    pool_users = 0
    pool_characters = 0
    additional_sp: list[int] = []

    for user_id in snapshot.users_sorted:
        user = snapshot.users[user_id]
        chars = [snapshot.characters[cid] for cid in user.character_ids]
        in_pool = [c for c in chars if not pool or c.group in pool]
        pool_characters += len(in_pool)
        if in_pool:
            pool_users += 1
        matching = [c for c in in_pool if character_matches(root, c)]
        matching_ids = {c.character_id for c in matching}
        additional_sp.extend(
            character_gap(root, c, snapshot.skills)
            for c in in_pool
            if c.character_id not in matching_ids
        )
        main = snapshot.characters[user.main_character_id]
        row = UserRow(
            user_id=user.user_id,
            user_name=user.user_name,
            main_character=MainCharacterOut(
                character_id=main.character_id,
                name=main.name,
                group=main.group,
                matches=any(c.character_id == main.character_id for c in matching),
            ),
            matching_characters=[
                CharacterOut(character_id=c.character_id, name=c.name, group=c.group)
                for c in matching
            ],
            match_count=len(matching),
            total_characters=len(in_pool),
        )
        if matching:
            matching_rows.append(row)
        elif include_non_matching:
            # Includes users with zero pool characters (0/0 rows).
            empty_rows.append(row)

    # users_sorted gives the name-ascending tiebreak; sort() is stable.
    matching_rows.sort(key=lambda r: -r.match_count)

    return QueryResponse(
        rows=[*matching_rows, *empty_rows],
        totals=QueryTotals(
            users_with_matches=len(matching_rows),
            total_matching_characters=sum(r.match_count for r in matching_rows),
            total_users=pool_users,
            total_characters=pool_characters,
        ),
        snapshot_version=snapshot.version,
        snapshot_fetched_at=datetime.fromtimestamp(snapshot.fetched_at, tz=UTC).isoformat(),
        additional_sp=additional_sp,
    )
