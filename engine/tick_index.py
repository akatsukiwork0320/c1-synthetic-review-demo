"""Persistent exact tick rows and a sparse lazy liquidity interval index.

The two structures are intentionally separate: set_tick does not call
add_range.  Their consistency and domain-level liquidity validity belong to
the caller, which updates both in the same SQLite transaction/savepoint.
No method commits or starts a transaction.  Mutations require an active one.
"""
from __future__ import annotations

import sqlite3


MIN_TICK = -887272
MAX_TICK = 887272
_UINT128_LIMIT = 1 << 128
_INT128_LIMIT = 1 << 127
_DELTA_LIMIT = 1 << 160


def _tick(value: int) -> None:
    if type(value) is not int or not MIN_TICK <= value <= MAX_TICK:
        raise ValueError("tick must be a canonical integer in the tick domain")


class TickIndex:
    """SQLite-backed point rows and range additions over the fixed tick domain.

    A missing tree node represents zeros relative to its ancestors' lazy
    additions.  Node minima/maxima include their own lazy addition.  Children
    exclude the parent's addition, so updates never need to push a lazy value
    into every descendant.  Integer heap IDs give keyed point SQL lookups.

    Each range update touches O(log U) nodes for U=MAX_TICK-MIN_TICK+1.
    The recursion stack uses O(log U) Python memory, excluding SQLite's cache.
    SQLite lookup/update costs are additional B-tree costs.  at() follows one
    path; extrema() reads only the root.  iter_ticks() streams sorted rows.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def _require_transaction(self) -> None:
        if not self.connection.in_transaction:
            raise RuntimeError("TickIndex mutations require the caller's transaction")

    def initialize_empty(self) -> None:
        """Create the schema and clear both structures inside the caller's tx.

        Call only for a fresh/reset state, not when reopening a saved index.
        DDL and clearing are transactional; this method never commits.
        """
        self._require_transaction()
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS ticks ("
            "i INTEGER PRIMARY KEY, gross TEXT NOT NULL, net TEXT NOT NULL)"
        )
        self.connection.execute(
            "CREATE TABLE IF NOT EXISTS segments ("
            "node INTEGER PRIMARY KEY, minimum TEXT NOT NULL, "
            "maximum TEXT NOT NULL, lazy TEXT NOT NULL)"
        )
        self.connection.execute("DELETE FROM ticks")
        self.connection.execute("DELETE FROM segments")
        self._write_node(1, 0, 0, 0)

    def set_tick(self, i: int, gross: int, net: int) -> None:
        """Set one uint128/int128 tick row, or remove the exact pair (0,0)."""
        _tick(i)
        if (
            type(gross) is not int
            or type(net) is not int
            or not 0 <= gross < _UINT128_LIMIT
            or not -_INT128_LIMIT <= net < _INT128_LIMIT
            or abs(net) > gross
        ):
            raise ValueError("gross/net violate the canonical uint128/int128 tick domain")
        self._require_transaction()
        if gross == 0:
            self.connection.execute("DELETE FROM ticks WHERE i=?", (i,))
        else:
            self.connection.execute(
                "INSERT INTO ticks(i,gross,net) VALUES(?,?,?) "
                "ON CONFLICT(i) DO UPDATE SET gross=excluded.gross,net=excluded.net",
                (i, str(gross), str(net)),
            )

    def get_tick(self, i: int) -> tuple[int, int]:
        _tick(i)
        row = self.connection.execute("SELECT gross,net FROM ticks WHERE i=?", (i,)).fetchone()
        return (0, 0) if row is None else (int(row[0]), int(row[1]))

    def _node(self, node: int) -> tuple[int, int, int]:
        row = self.connection.execute(
            "SELECT minimum,maximum,lazy FROM segments WHERE node=?", (node,)
        ).fetchone()
        return (0, 0, 0) if row is None else (int(row[0]), int(row[1]), int(row[2]))

    def _write_node(self, node: int, minimum: int, maximum: int, lazy: int) -> None:
        self.connection.execute(
            "INSERT INTO segments(node,minimum,maximum,lazy) VALUES(?,?,?,?) "
            "ON CONFLICT(node) DO UPDATE SET "
            "minimum=excluded.minimum,maximum=excluded.maximum,lazy=excluded.lazy",
            (node, str(minimum), str(maximum), str(lazy)),
        )

    def add_range(self, lo: int, hi: int, delta: int) -> None:
        """Add an exact integer to inclusive [lo,hi], with no clipping.

        Negative additions and negative intermediate liquidity are supported:
        the caller checks extrema against its state domain and can roll back.
        Input deltas satisfy abs(delta)<2**160.  Arithmetic results remain
        exact Python integers; they are not silently clipped or wrapped.
        """
        _tick(lo)
        _tick(hi)
        if lo > hi or type(delta) is not int or not -_DELTA_LIMIT < delta < _DELTA_LIMIT:
            raise ValueError("range must be ordered and delta a canonical integer with abs(delta)<2**160")
        self._require_transaction()
        if delta:
            self._add(1, MIN_TICK, MAX_TICK, lo, hi, delta)

    def _add(self, node: int, left: int, right: int, lo: int, hi: int, delta: int) -> None:
        minimum, maximum, lazy = self._node(node)
        if lo <= left and right <= hi:
            self._write_node(node, minimum + delta, maximum + delta, lazy + delta)
            return
        middle = (left + right) // 2
        if lo <= middle:
            self._add(node * 2, left, middle, lo, hi, delta)
        if hi > middle:
            self._add(node * 2 + 1, middle + 1, right, lo, hi, delta)
        left_min, left_max, _left_lazy = self._node(node * 2)
        right_min, right_max, _right_lazy = self._node(node * 2 + 1)
        self._write_node(
            node,
            lazy + min(left_min, right_min),
            lazy + max(left_max, right_max),
            lazy,
        )

    def at(self, tick: int) -> int:
        _tick(tick)
        node, left, right, total = 1, MIN_TICK, MAX_TICK, 0
        while True:
            _minimum, _maximum, lazy = self._node(node)
            total += lazy
            if left == right:
                return total
            middle = (left + right) // 2
            if tick <= middle:
                node, right = node * 2, middle
            else:
                node, left = node * 2 + 1, middle + 1

    def extrema(self) -> tuple[int, int]:
        minimum, maximum, _lazy = self._node(1)
        return minimum, maximum

    def iter_ticks(self):
        """Yield (index,gross,net) without fetching the complete table."""
        cursor = self.connection.execute("SELECT i,gross,net FROM ticks ORDER BY i")
        try:
            for i, gross, net in cursor:
                yield i, int(gross), int(net)
        finally:
            cursor.close()
