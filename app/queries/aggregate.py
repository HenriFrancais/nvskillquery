"""Run a query tree over a snapshot and aggregate matches per user.

The response models live here (not in the API layer) so the whole
query pipeline — tree → evaluate → aggregate — is pure and testable
without HTTP.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel

from app.queries.evaluate import character_matches
from app.queries.tree import AnyQueryNode
from app.snapshot.models import Snapshot


class CharacterOut(BaseModel):
    character_id: int
    name: str
    character_type: str


class MainCharacterOut(CharacterOut):
    matches: bool


class UserRow(BaseModel):
    user_id: int
    user_name: str
    main_character: MainCharacterOut
    matching_characters: list[CharacterOut]
    match_count: int
    total_characters: int


class QueryTotals(BaseModel):
    users_with_matches: int
    total_matching_characters: int
    total_users: int
    total_characters: int


class QueryResponse(BaseModel):
    rows: list[UserRow]
    totals: QueryTotals
    snapshot_version: int
    snapshot_fetched_at: str  # ISO 8601


def run_query(
    snapshot: Snapshot,
    root: AnyQueryNode,
    include_non_matching: bool = False,
) -> QueryResponse:
    matching_rows: list[UserRow] = []
    empty_rows: list[UserRow] = []

    for user_id in snapshot.users_sorted:
        user = snapshot.users[user_id]
        chars = [snapshot.characters[cid] for cid in user.character_ids]
        matching = [c for c in chars if character_matches(root, c)]
        main = chars[0]  # character_ids puts the main first
        row = UserRow(
            user_id=user.user_id,
            user_name=user.user_name,
            main_character=MainCharacterOut(
                character_id=main.character_id,
                name=main.name,
                character_type=main.character_type,
                matches=any(c.character_id == main.character_id for c in matching),
            ),
            matching_characters=[
                CharacterOut(
                    character_id=c.character_id,
                    name=c.name,
                    character_type=c.character_type,
                )
                for c in matching
            ],
            match_count=len(matching),
            total_characters=len(chars),
        )
        if matching:
            matching_rows.append(row)
        elif include_non_matching:
            empty_rows.append(row)

    # users_sorted gives the name-ascending tiebreak; sort() is stable.
    matching_rows.sort(key=lambda r: -r.match_count)

    return QueryResponse(
        rows=[*matching_rows, *empty_rows],
        totals=QueryTotals(
            users_with_matches=len(matching_rows),
            total_matching_characters=sum(r.match_count for r in matching_rows),
            total_users=len(snapshot.users),
            total_characters=len(snapshot.characters),
        ),
        snapshot_version=snapshot.version,
        snapshot_fetched_at=datetime.fromtimestamp(snapshot.fetched_at, tz=UTC).isoformat(),
    )
