"""Atomic, disk-backed CORE/TICKS replay under explicit model assumptions.

This is a new P5 wrapper. It does not call or weaken the synthetic Store or
evidence gates. The tick index and integer reference invariants are pinned
copies; source coverage, header authenticity and bytecode applicability are
the caller's separately reported premises. A successful snapshot describes
only the committed prefix under those premises.

Every Mint/Burn checks changed endpoints and global prefix-liquidity extrema.
It does not re-scan interior ticks for endpoint-closing feasibility. The
caller's final full reference-invariant pass must report that separate check.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

try:
    from .tick_index import TickIndex
    from .ref_invariants import (MIN_TICK, MAX_TICK, MIN_SQRT_RATIO,
                                 MAX_SQRT_RATIO, boundary_check,
                                 max_liquidity_for_spacing, sqrt_ratio_at_tick)
except ImportError:
    from tick_index import TickIndex
    from ref_invariants import (MIN_TICK, MAX_TICK, MIN_SQRT_RATIO,
                                MAX_SQRT_RATIO, boundary_check,
                                max_liquidity_for_spacing, sqrt_ratio_at_tick)

U128 = 1 << 128
I128 = 1 << 127
NOOPS = frozenset({"Collect", "Flash", "CollectProtocol", "SetFeeProtocol",
                   "IncreaseObservationCardinalityNext"})
KINDS = ("Mint", "Burn", "Swap", "Collect", "Flash", "CollectProtocol",
         "SetFeeProtocol", "IncreaseObservationCardinalityNext")
ASSUMPTIONS = (
    "ASSUMED_MODEL: pinned Uniswap v3 reference event semantics apply",
    "Anchor is the caller-bound complete initialized CORE/TICKS state",
    "Replay ordering and provider-relative coverage are caller-bound premises",
    "No receipt, consensus, canonical ancestry, or deployed-bytecode proof is asserted",
)


class ReplayError(ValueError):
    """A schema, binding, ordering, or conditional-model constraint failed."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False)


def _integer(value, name, lo=None, hi=None):
    if (type(value) is not int or (lo is not None and value < lo)
            or (hi is not None and value >= hi)):
        raise ReplayError(name)
    return value


def _digest(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ReplayError("CHUNK_DIGEST")
    return value


def fast_boundary_valid(sqrt_price, tick):
    """Same necessary boundary predicate as reference boundary_check().

    The upper equality is the exact downward-crossing case. Two forward
    TickMath evaluations avoid a fresh inverse binary search for each Swap.
    This predicate does not prove swap execution or crossing direction.
    """
    if (type(sqrt_price) is not int or type(tick) is not int
            or not MIN_SQRT_RATIO <= sqrt_price < MAX_SQRT_RATIO
            or not MIN_TICK <= tick <= MAX_TICK):
        return False
    if sqrt_price < sqrt_ratio_at_tick(tick):
        return False
    return tick == MAX_TICK or sqrt_price <= sqrt_ratio_at_tick(tick + 1)


class ReplayStore:
    """One SQLite writer; seed once and atomically commit complete chunks.

    begin_chunk uses positive, contiguous ordinals starting at one. It returns
    False for an already committed ordinal with the identical bound digest;
    in that case the caller must skip its body and must not call commit_chunk.
    Any apply failure rolls the entire pending chunk back. A failed instance
    must be closed before retry; its snapshot is Invalid with no state value.
    """
    def __init__(self, db_path, binding: dict):
        if type(binding) is not dict:
            raise ReplayError("BINDING_SCHEMA")
        try:
            binding_text = _canonical(binding)
        except (ValueError, TypeError, RecursionError) as exc:
            raise ReplayError("BINDING_SCHEMA") from exc
        if len(binding_text.encode("ascii")) > 262144:
            raise ReplayError("BINDING_LIMIT")
        self.binding = hashlib.sha256(binding_text.encode("ascii")).hexdigest()
        self.connection = sqlite3.connect(str(db_path), isolation_level=None, timeout=5)
        self._active_chunk = None
        self._chunk_after_block = None
        self.failure = None
        try:
            for pragma in ("journal_mode=DELETE", "synchronous=EXTRA", "cache_size=-2048",
                           "temp_store=FILE", "mmap_size=0", "max_page_count=1048576"):
                self.connection.execute("PRAGMA " + pragma)
            self.index = TickIndex(self.connection)
            exists = self.connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='replay_meta'").fetchone()
            if not exists:
                if self.connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table'").fetchone():
                    raise ReplayError("DATABASE_NOT_EMPTY")
                self.connection.execute("BEGIN IMMEDIATE")
                self.connection.execute("CREATE TABLE replay_meta (id INTEGER PRIMARY KEY CHECK(id=1), binding TEXT NOT NULL, binding_json TEXT NOT NULL, state TEXT NOT NULL)")
                self.connection.execute("CREATE TABLE checkpoints (ordinal INTEGER PRIMARY KEY, digest TEXT NOT NULL, range_end INTEGER NOT NULL, event_count INTEGER NOT NULL)")
                self.index.initialize_empty()
                initial = {"seeded": False, "s": 0, "tick": 0, "liquidity": 0,
                           "spacing": None, "max_liquidity_per_tick": None,
                           "tick_count": 0, "last_order": None, "seed_digest": None,
                           "counts": {"events": 0, **{kind: 0 for kind in KINDS}}}
                self.connection.execute("INSERT INTO replay_meta VALUES(1,?,?,?)",
                                        (self.binding, binding_text, _canonical(initial)))
                self.connection.execute("COMMIT")
            row = self.connection.execute(
                "SELECT binding,binding_json,state FROM replay_meta WHERE id=1").fetchone()
            if row is None or row[0] != self.binding or row[1] != binding_text:
                raise ReplayError("RESUME_BINDING_CONFLICT")
            self.state = json.loads(row[2])
        except BaseException:
            if self.connection.in_transaction:
                self.connection.execute("ROLLBACK")
            self.connection.close()
            raise

    @property
    def is_seeded(self):
        return self.state["seeded"]

    def _save(self):
        self.connection.execute("UPDATE replay_meta SET state=? WHERE id=1",
                                (_canonical(self.state),))

    def _reload(self):
        self.state = json.loads(self.connection.execute(
            "SELECT state FROM replay_meta WHERE id=1").fetchone()[0])

    @staticmethod
    def _seed_row(row):
        if type(row) not in (tuple, list):
            raise ReplayError("ANCHOR_TICK_SCHEMA")
        if len(row) == 3:
            return row[0], row[1], row[2]
        if len(row) == 2 and type(row[1]) is dict:
            values = row[1]
            if values.get("initialized") is not True:
                raise ReplayError("ANCHOR_TICK_INITIALIZED")
            try:
                return row[0], values["liquidityGross"], values["liquidityNet"]
            except KeyError as exc:
                raise ReplayError("ANCHOR_TICK_SCHEMA") from exc
        raise ReplayError("ANCHOR_TICK_SCHEMA")

    def _tick_row_valid(self, i, gross, net, *, stored):
        _integer(i, "TICK_DOMAIN", MIN_TICK, MAX_TICK + 1)
        _integer(gross, "GROSS_DOMAIN", 1 if stored else 0, U128)
        _integer(net, "NET_DOMAIN", -I128, I128)
        if i % self.state["spacing"]:
            raise ReplayError("TICK_SPACING")
        if abs(net) > gross:
            raise ReplayError("GROSS_NET_CONTRADICTION")
        if gross > self.state["max_liquidity_per_tick"]:
            raise ReplayError("MAX_LIQUIDITY_PER_TICK")
        if (gross + net) % 2 or (gross - net) % 2:
            raise ReplayError("ENDPOINT_PARITY")

    def seed(self, slot0, liquidity, spacing, max_liquidity_per_tick, ticks_iter):
        """Consume sorted (tick,gross,net) or (tick,P4-values) rows once.

        This validates numeric/endpoint completeness necessities; a bitmap
        census and source completeness remain the supplied anchor's premises.
        Seeding is one transaction and is never repeated on a resumed store.
        """
        if self.connection.in_transaction or self.is_seeded:
            raise ReplayError("SEED_ORDER")
        if type(slot0) is not dict:
            raise ReplayError("ANCHOR_CORE_SCHEMA")
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            try:
                s, tick = slot0["sqrtPriceX96"], slot0["tick"]
                if boundary_check(slot0)["violations"]:
                    raise ReplayError("EXACT_TICKMATH_BOUNDARY")
            except (KeyError, ValueError, TypeError) as exc:
                if isinstance(exc, ReplayError):
                    raise
                raise ReplayError("ANCHOR_CORE_SCHEMA") from exc
            _integer(liquidity, "LIQUIDITY_DOMAIN", 0, U128)
            _integer(spacing, "TICK_SPACING", 1, 1 << 23)
            _integer(max_liquidity_per_tick, "MAX_LIQUIDITY_PER_TICK", 1, U128)
            if max_liquidity_per_tick != max_liquidity_for_spacing(spacing):
                raise ReplayError("MAX_LIQUIDITY_PER_TICK")
            self.state.update(s=s, tick=tick, liquidity=liquidity, spacing=spacing,
                              max_liquidity_per_tick=max_liquidity_per_tick)
            running = 0
            previous = None
            seed_hash = hashlib.sha256(_canonical(
                [s, tick, liquidity, spacing, max_liquidity_per_tick]).encode("ascii"))
            for row in ticks_iter:
                i, gross, net = self._seed_row(row)
                self._tick_row_valid(i, gross, net, stored=True)
                if previous is not None and i <= previous:
                    raise ReplayError("ANCHOR_TICK_ORDER")
                if (gross - net) // 2 > running:
                    raise ReplayError("ENDPOINT_CLOSING")
                if previous is not None and running:
                    self.index.add_range(previous, i - 1, running)
                self.index.set_tick(i, gross, net)
                running += net
                if not 0 <= running < U128:
                    raise ReplayError("PREFIX_LIQUIDITY_DOMAIN")
                previous = i
                self.state["tick_count"] += 1
                seed_hash.update((_canonical([i, gross, net]) + "\n").encode("ascii"))
            if running:
                raise ReplayError("ANCHOR_NET_TOTAL")
            self._check_active(liquidity, tick)
            self.state.update(seeded=True, seed_digest=seed_hash.hexdigest())
            self._save()
            self.connection.execute("COMMIT")
        except BaseException:
            self.connection.execute("ROLLBACK")
            self._reload()
            raise

    def checkpoint(self):
        row = self.connection.execute(
            "SELECT ordinal,digest,range_end,event_count FROM checkpoints ORDER BY ordinal DESC LIMIT 1").fetchone()
        return None if row is None else dict(zip(
            ("ordinal", "digest", "range_end", "event_count"), row))

    def begin_chunk(self, ordinal, digest):
        if self.failure is not None:
            raise ReplayError("FAILED_INSTANCE_REQUIRES_REOPEN")
        if self.connection.in_transaction or not self.is_seeded:
            raise ReplayError("CHUNK_ORDER")
        _integer(ordinal, "CHUNK_ORDINAL", 1, 1 << 63)
        _digest(digest)
        old = self.connection.execute("SELECT digest FROM checkpoints WHERE ordinal=?",
                                      (ordinal,)).fetchone()
        if old is not None:
            if old[0] != digest:
                raise ReplayError("CHUNK_DIGEST_CONFLICT")
            return False
        latest = self.checkpoint()
        if ordinal != (1 if latest is None else latest["ordinal"] + 1):
            raise ReplayError("CHUNK_ORDINAL_GAP")
        self.connection.execute("BEGIN IMMEDIATE")
        self._active_chunk = (ordinal, digest)
        self._chunk_after_block = None if latest is None else latest["range_end"]
        return True

    def _check_active(self, liquidity, tick):
        minimum, maximum = self.index.extrema()
        if minimum < 0 or maximum >= U128:
            raise ReplayError("PREFIX_LIQUIDITY_DOMAIN")
        if not 0 <= liquidity < U128 or self.index.at(tick) != liquidity:
            raise ReplayError("ACTIVE_LIQUIDITY_MISMATCH")
        # Total net is zero at seed. Every later update ends at upper-1,
        # strictly below MAX_TICK, preserving the terminal zero structurally.

    def apply(self, event):
        """Apply event_decoder's normalized event; no raw log is retained."""
        if self._active_chunk is None or not self.connection.in_transaction:
            raise ReplayError("APPLY_REQUIRES_CHUNK")
        try:
            self._apply(event)
        except BaseException as exc:
            self.rollback_chunk()
            self.failure = getattr(exc, "code", type(exc).__name__)
            raise

    def _apply(self, event):
        if type(event) is not dict or type(event.get("args")) is not dict:
            raise ReplayError("EVENT_SCHEMA")
        if event.get("removed", False) is not False:
            raise ReplayError("REMOVED_LOG")
        try:
            order = [_integer(event[k], "EVENT_LOCATION", 0, 1 << 63)
                     for k in ("block_number", "transaction_index", "log_index")]
            kind, args = event["event_kind"], event["args"]
        except KeyError as exc:
            raise ReplayError("EVENT_SCHEMA") from exc
        if type(kind) is not str or kind not in KINDS:
            raise ReplayError("INITIALIZE_AFTER_ANCHOR" if kind == "Initialize" else "UNSUPPORTED_EVENT")
        last = self.state["last_order"]
        if last is not None and (order <= last or (order[0] == last[0] and order[2] <= last[2])):
            raise ReplayError("EVENT_ORDER")
        if self._chunk_after_block is not None and order[0] <= self._chunk_after_block:
            raise ReplayError("EVENT_BEFORE_CHECKPOINT")
        s, tick, liquidity = self.state["s"], self.state["tick"], self.state["liquidity"]
        try:
            if kind == "Swap":
                s = _integer(args["sqrt_price_x96"], "PRICE_DOMAIN", MIN_SQRT_RATIO, MAX_SQRT_RATIO)
                tick = _integer(args["tick"], "TICK_DOMAIN", MIN_TICK, MAX_TICK + 1)
                liquidity = _integer(args["liquidity"], "LIQUIDITY_DOMAIN", 0, U128)
                if not fast_boundary_valid(s, tick):
                    raise ReplayError("EXACT_TICKMATH_BOUNDARY")
                self._check_active(liquidity, tick)
            elif kind in {"Mint", "Burn"}:
                lower = _integer(args["lower"], "TICK_DOMAIN", MIN_TICK, MAX_TICK + 1)
                upper = _integer(args["upper"], "TICK_DOMAIN", MIN_TICK, MAX_TICK + 1)
                amount = _integer(args["amount"], "AMOUNT_SUPPORTED_DOMAIN", 1 if kind == "Mint" else 0, I128)
                if lower >= upper or lower % self.state["spacing"] or upper % self.state["spacing"]:
                    raise ReplayError("TICK_RANGE_OR_SPACING")
                delta = amount if kind == "Mint" else -amount
                for i, sign in ((lower, 1), (upper, -1)):
                    gross, net = self.index.get_tick(i)
                    next_gross, next_net = gross + delta, net + sign * delta
                    self._tick_row_valid(i, next_gross, next_net, stored=False)
                    self.index.set_tick(i, next_gross, next_net)
                    self.state["tick_count"] += int(next_gross > 0) - int(gross > 0)
                self.index.add_range(lower, upper - 1, delta)
                if lower <= tick < upper:
                    liquidity += delta
                self._check_active(liquidity, tick)
            # Other supported events have no effect on this declared projection.
        except KeyError as exc:
            raise ReplayError("EVENT_ARGS_SCHEMA") from exc
        self.state.update(s=s, tick=tick, liquidity=liquidity, last_order=order)
        self.state["counts"]["events"] += 1
        self.state["counts"][kind] += 1

    def commit_chunk(self, ordinal, digest, range_end):
        if self._active_chunk != (ordinal, digest) or not self.connection.in_transaction:
            raise ReplayError("CHUNK_COMMIT_BINDING")
        try:
            _integer(range_end, "CHUNK_RANGE_END", 0, 1 << 63)
            previous = self.checkpoint()
            if previous is not None and range_end <= previous["range_end"]:
                raise ReplayError("CHUNK_RANGE_ORDER")
            if self.state["last_order"] is not None and self.state["last_order"][0] > range_end:
                raise ReplayError("EVENT_AFTER_CHUNK_RANGE")
            self._save()
            self.connection.execute("INSERT INTO checkpoints VALUES(?,?,?,?)",
                                    (ordinal, digest, range_end, self.state["counts"]["events"]))
            self.connection.execute("COMMIT")
            self._active_chunk = None
            self._chunk_after_block = None
        except BaseException:
            self.rollback_chunk()
            raise

    def rollback_chunk(self):
        if self.connection.in_transaction:
            self.connection.execute("ROLLBACK")
        self._active_chunk = None
        self._chunk_after_block = None
        self._reload()

    def snapshot(self):
        """Return only committed state; failures never expose a known value."""
        if self.connection.in_transaction:
            raise ReplayError("SNAPSHOT_REQUIRES_COMMIT")
        good = self.is_seeded and self.failure is None
        return {"schema": "c1-p5-replay-state/1", "evidence_class": "ASSUMED_MODEL",
                "status": "Known" if good else "Invalid" if self.failure else "Unknown",
                "reason": self.failure or ("CONDITIONAL_MODEL_REPLAY" if good else "ANCHOR_NOT_SEEDED"),
                "core": {"sqrtPriceX96": str(self.state["s"]), "tick": self.state["tick"],
                         "liquidity": str(self.state["liquidity"])} if good else None,
                "counts": dict(self.state["counts"]),
                "last_order": None if self.state["last_order"] is None else list(self.state["last_order"]),
                "tick_count": self.state["tick_count"], "checkpoint": self.checkpoint(),
                "seed_digest": self.state["seed_digest"], "assumptions": list(ASSUMPTIONS),
                "verification_scope": "Necessary CORE/TICKS constraints under assumptions; no execution proof"}

    def iter_ticks(self):
        if self.connection.in_transaction or self.failure is not None or not self.is_seeded:
            raise ReplayError("TICKS_REQUIRES_VALID_COMMIT")
        yield from self.index.iter_ticks()

    def close(self):
        try:
            if self.connection.in_transaction:
                self.rollback_chunk()
        finally:
            self.connection.close()
