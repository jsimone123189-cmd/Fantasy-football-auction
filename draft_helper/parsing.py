"""Helpers for Yahoo Fantasy API's JSON shape.

Yahoo's JSON is notoriously irregular:
  * "Collections" (teams, players, draft_results, leagues, ...) are objects
    keyed by stringified index ("0", "1", ...) plus a "count" key.
  * A single "resource" (one team, one player, the league record itself) is
    often serialized as a list of small single-key dict "fragments" that are
    meant to be merged into one flat dict, e.g.
        [{"team_key": "..."}, {"name": "..."}, {"managers": [...]}, ...]

These helpers normalize both patterns defensively. If Yahoo's actual response
diverges from what's expected here, callers should catch and skip rather than
blow up the whole fetch — see yahoo_client.py's `_safe` wrapper and the
`debug-endpoint` CLI command for inspecting raw responses when that happens.
"""
from __future__ import annotations

from typing import Any, Iterator


def iter_collection(obj: Any) -> Iterator[Any]:
    """Yield each item in a Yahoo "collection" object (dict with "0", "1", ..., "count")."""
    if obj is None:
        return
    if isinstance(obj, list):
        # Some endpoints return a plain list instead of an indexed dict.
        for item in obj:
            yield item
        return
    if not isinstance(obj, dict):
        return
    count = obj.get("count")
    if count is not None:
        for i in range(int(count)):
            item = obj.get(str(i))
            if item is not None:
                yield item
    else:
        for k, v in obj.items():
            if k == "count":
                continue
            yield v


def merge_fragments(obj: Any) -> dict:
    """Flatten a Yahoo "list of single-key fragment dicts" resource into one dict.

    Handles the common extra nesting level where the list itself is wrapped in
    another single-element list, e.g. `[[{"a": 1}, {"b": 2}]]`.
    """
    result: dict = {}

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            result.update(node)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(obj)
    return result


def first(obj: Any) -> Any:
    """Return obj[0] if obj is a non-empty list, else obj itself."""
    if isinstance(obj, list):
        return obj[0] if obj else None
    return obj
