"""Render a QueryResponse as CSV for export to other tools."""

from __future__ import annotations

import csv
import io

from app.queries.aggregate import QueryResponse

HEADER = [
    "user_name",
    "main_character",
    "main_character_group",
    "main_character_matches",
    "match_count",
    "total_characters",
    "matching_characters",
]


def query_response_to_csv(resp: QueryResponse) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    for row in resp.rows:
        writer.writerow(
            [
                row.user_name,
                row.main_character.name,
                row.main_character.group,
                "yes" if row.main_character.matches else "no",
                row.match_count,
                row.total_characters,
                "; ".join(
                    f"{c.name} ({c.group})" for c in row.matching_characters
                ),
            ]
        )
    return buf.getvalue()
