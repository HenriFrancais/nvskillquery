"""Render a QueryResponse as CSV for export to other tools."""

from __future__ import annotations

import csv
import io

from app.queries.aggregate import QueryResponse
from app.queries.doctrine import DoctrineLabel

HEADER = [
    "user_name",
    "match_count",
    "total_characters",
    "matching_characters",
]


def query_response_to_csv(resp: QueryResponse, doctrine: DoctrineLabel | None = None) -> str:
    buf = io.StringIO()
    if doctrine is not None:
        identity = " / ".join(
            p
            for p in (doctrine.doctrine, doctrine.role, doctrine.ship_type, doctrine.fit_name)
            if p
        )
        buf.write(
            f"# Doctrine: {identity} — {doctrine.tier} tier ({doctrine.skill_count} skills)\n"
        )
    writer = csv.writer(buf)
    writer.writerow(HEADER)
    for row in resp.rows:
        writer.writerow(
            [
                row.user_name,
                row.match_count,
                row.total_characters,
                "; ".join(
                    f"{c.name} ({c.group})" for c in row.matching_characters
                ),
            ]
        )
    return buf.getvalue()
