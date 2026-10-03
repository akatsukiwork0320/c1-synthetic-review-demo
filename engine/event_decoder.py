"""Strict local event decoding for the separate ASSUMED_MODEL replay path.

``reference_abi.py`` is a byte-identical copy of the public static decoder in
abi_adapter_v1.  Its representation checks do not establish authenticity,
coverage, finality, bytecode correspondence, or model correctness.  This module
never imports or calls that unit's synthetic evidence gate, adapter, or solver.

Only the explicitly named CORE_TICKS projection is supported.  Under the
assumed canonical v3 model, Collect, Flash, CollectProtocol, SetFeeProtocol,
and IncreaseObservationCardinalityNext do not change sqrtPriceX96, tick,
active liquidity, or tick liquidityGross/liquidityNet.  Their entire ABI is
still decoded and retained.  This statement does not cover positions, fees,
oracle state, token balances, transfers, or other economic quantities.
"""
from __future__ import annotations

import re
from typing import Iterable

try:
    from .reference_abi import ABIError, UnknownEvent, _quantity, decode_log
except ImportError:
    from reference_abi import ABIError, UnknownEvent, _quantity, decode_log


REFERENCE_ABI_SHA256 = "dd3e97fe55ae68f8fbaf22d5138a649914c8b6ed8ba80e555789242794013097"
PROJECTION = "CORE_TICKS"
NO_CORE_TICK_EFFECT = frozenset({
    "Collect", "Flash", "CollectProtocol", "SetFeeProtocol",
    "IncreaseObservationCardinalityNext",
})
_RENAMES = {
    "sqrtPriceX96": "sqrt_price_x96", "tickLower": "lower", "tickUpper": "upper",
    "feeProtocol0Old": "fee_protocol0_old", "feeProtocol1Old": "fee_protocol1_old",
    "feeProtocol0New": "fee_protocol0_new", "feeProtocol1New": "fee_protocol1_new",
    "observationCardinalityNextOld": "observation_cardinality_next_old",
    "observationCardinalityNextNew": "observation_cardinality_next_new",
}
_IDENTITY_FIELDS = (
    "address", "block_number", "block_hash", "transaction_hash",
    "transaction_index", "log_index", "removed",
)
_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
_HASH = re.compile(r"0x[0-9a-f]{64}")
_MAX_COORDINATE = 1 << 63
_TICK_LIMIT = 887272


class DecodeError(ValueError):
    """Value-free fail-closed diagnosis suitable for a public run report."""

    def __init__(self, code: str, status: str = "Invalid"):
        if status not in {"Unknown", "Invalid"}:
            raise ValueError("unsupported decode status")
        self.code, self.status = code, status
        super().__init__(code)


def _configuration(pool, tick_spacing, initialized, projection):
    if type(pool) is not str or _ADDRESS.fullmatch(pool) is None:
        raise DecodeError("POOL_SCHEMA")
    if type(tick_spacing) is not int or not 0 < tick_spacing < (1 << 23):
        raise DecodeError("TICK_SPACING_SCHEMA")
    if type(initialized) is not bool:
        raise DecodeError("INITIALIZED_SCHEMA")
    if projection != PROJECTION:
        raise DecodeError("PROJECTION_UNMODELED", "Unknown")
    return pool.lower()


def decode_event(raw: dict, *, pool: str, tick_spacing: int,
                 projection: str, initialized: bool = True) -> dict:
    """Decode one supplied pool log; retain every ABI field as exact integers.

    ``projection='CORE_TICKS'`` is a required caller assertion of query scope,
    not a verification flag.  The caller must separately establish saved-input
    coverage and header binding, then feed every result to ``EventOrder``.
    No event omission, replay, filesystem read, or external request occurs here.

    The optional transport field ``blockTimestamp`` must be a canonical RPC
    quantity. It is removed only from a shallow decoder-input copy; original
    source bytes remain the provenance. It does not affect CORE_TICKS or enter
    the normalized result. All required fields and other extra fields remain
    subject to the unchanged strict reference envelope check.
    """
    expected_pool = _configuration(pool, tick_spacing, initialized, projection)
    try:
        strict_raw = raw
        if type(raw) is dict and "blockTimestamp" in raw:
            _quantity(raw["blockTimestamp"])
            strict_raw = {key: value for key, value in raw.items() if key != "blockTimestamp"}
        decoded = decode_log(strict_raw)
    except UnknownEvent as error:
        raise DecodeError(error.code, "Unknown") from None
    except ABIError as error:
        raise DecodeError(error.code) from None
    if decoded["address"] != expected_pool:
        raise DecodeError("POOL_BINDING")
    if any(not 0 <= decoded[key] < _MAX_COORDINATE
           for key in ("block_number", "transaction_index", "log_index")):
        raise DecodeError("LOG_INTEGER_LIMIT")
    if decoded["removed"]:
        raise DecodeError("REMOVED_LOG", "Unknown")

    kind = decoded["kind"]
    args = {_RENAMES.get(key, key): value for key, value in decoded["fields"].items()}
    if kind == "Initialize" and initialized:
        raise DecodeError("INITIALIZE_AFTER_INITIALIZED_ANCHOR")
    # Canonical v3 Collect skips checkTicks and can emit for an empty position
    # key. Its endpoints remain strict int24 ABI values, but need not form a
    # valid liquidity range. Only Mint/Burn use these CORE_TICKS constraints.
    if kind in {"Mint", "Burn"}:
        if not -_TICK_LIMIT <= args["lower"] < args["upper"] <= _TICK_LIMIT:
            raise DecodeError("TICK_RANGE")
        if args["lower"] % tick_spacing or args["upper"] % tick_spacing:
            raise DecodeError("TICK_SPACING")
    if kind in {"Mint", "Burn"}:
        if not (1 if kind == "Mint" else 0) <= args["amount"] < (1 << 127):
            raise DecodeError("LIQUIDITY_DELTA_DOMAIN")
        core = {key: args[key] for key in ("lower", "upper", "amount")}
    elif kind in {"Swap", "Initialize"}:
        if not 0 < args["sqrt_price_x96"] < (1 << 160):
            raise DecodeError("SQRT_PRICE_DOMAIN")
        if not -_TICK_LIMIT <= args["tick"] <= _TICK_LIMIT:
            raise DecodeError("TICK_DOMAIN")
        keys = ("sqrt_price_x96", "tick", "liquidity") if kind == "Swap" else ("sqrt_price_x96", "tick")
        core = {key: args[key] for key in keys}
    elif kind in NO_CORE_TICK_EFFECT:
        core = None
    else:
        # Future additions to the pinned decoder must not acquire model support
        # merely by becoming ABI-decodable.
        raise DecodeError("EVENT_UNMODELED", "Unknown")
    identity = {key: decoded[key] for key in _IDENTITY_FIELDS}
    return {
        "event_kind": kind, "args": args, **identity,
        "order": (decoded["block_number"], decoded["transaction_index"], decoded["log_index"]),
        "projection": {
            "query": PROJECTION, "model_status": "ASSUMED_MODEL", "modeled": True,
            "effect": "NO_EFFECT" if core is None else "UPDATE", "data": core,
        },
    }


class EventOrder:
    """Constant-size original-order and adjacent identity binding validator.

    Every input pool event, including query-relative no-effect events, must be
    accepted.  Duplicates and disorder are rejected rather than sorted or
    silently deduplicated.  This does not prove that any missing log exists or
    that a transaction hash never recurs at a distant location; a caller's
    inventory/coverage layer is responsible for those global constraints.
    After an error the validator is poisoned and cannot accept more events.
    """

    def __init__(self):
        self._last = None
        self._failure = None

    def accept(self, event: dict) -> None:
        if self._failure is not None:
            raise DecodeError(self._failure)
        try:
            coordinates = tuple(event[key] for key in ("block_number", "transaction_index", "log_index"))
            if any(type(value) is not int or not 0 <= value < _MAX_COORDINATE for value in coordinates):
                raise DecodeError("ORDER_SCHEMA")
            hashes = tuple(event[key] for key in ("block_hash", "transaction_hash"))
            if any(type(value) is not str or _HASH.fullmatch(value) is None for value in hashes):
                raise DecodeError("ORDER_SCHEMA")
            current = coordinates + hashes
            if self._last is not None:
                old = self._last
                if coordinates <= old[:3] or (coordinates[0] == old[0] and coordinates[2] <= old[2]):
                    raise DecodeError("LOG_ORDER_CONFLICT")
                if coordinates[0] == old[0] and hashes[0] != old[3]:
                    raise DecodeError("BLOCK_IDENTITY_CONFLICT")
                if coordinates[0] != old[0] and hashes[0] == old[3]:
                    raise DecodeError("BLOCK_IDENTITY_CONFLICT")
                same_transaction = coordinates[:2] == old[:2]
                if (same_transaction and hashes[1] != old[4]) or (not same_transaction and hashes[1] == old[4]):
                    raise DecodeError("TRANSACTION_IDENTITY_CONFLICT")
            self._last = current
        except (KeyError, TypeError):
            self._failure = "ORDER_SCHEMA"
            raise DecodeError(self._failure) from None
        except DecodeError as error:
            self._failure = error.code
            raise


def decode_transaction(raw_logs: Iterable[dict], *, pool: str, tick_spacing: int,
                       projection: str, initialized: bool = True,
                       complete: bool = False, max_logs: int = 100000) -> dict:
    """Small bounded transaction helper; errors return no accepted events.

    ``complete`` is caller evidence, never inferred from successful decoding.
    The main replay path may instead stream ``decode_event`` and ``EventOrder``.
    A malformed, unknown, removed, mixed-transaction, or unmodeled member makes
    the entire returned transaction non-replayable.  No decoded partial prefix
    is returned.  Flags distinguish unmodeled evidence from malformed input.
    """
    if type(complete) is not bool or type(max_logs) is not int or not 0 < max_logs <= 100000:
        raise DecodeError("TRANSACTION_SCHEMA")
    _configuration(pool, tick_spacing, initialized, projection)
    events, issues = [], []
    order, transaction = EventOrder(), None
    count = 0
    try:
        for raw in raw_logs:
            count += 1
            if count > max_logs:
                raise DecodeError("TRANSACTION_LOG_LIMIT")
            event = decode_event(raw, pool=pool, tick_spacing=tick_spacing,
                                 projection=projection, initialized=initialized)
            binding = tuple(event[key] for key in ("block_number", "block_hash", "transaction_index", "transaction_hash"))
            if transaction is not None and binding != transaction:
                raise DecodeError("TRANSACTION_IDENTITY_CONFLICT")
            transaction = binding
            order.accept(event)
            events.append(event)
    except DecodeError as error:
        issues.append({"status": error.status, "code": error.code})
    except (TypeError, ValueError):
        issues.append({"status": "Invalid", "code": "TRANSACTION_SCHEMA"})
    if not complete:
        issues.append({"status": "Unknown", "code": "TRANSACTION_COVERAGE_UNCONFIRMED"})
    if count == 0:
        issues.append({"status": "Unknown", "code": "TRANSACTION_EMPTY"})
    status = "Invalid" if any(issue["status"] == "Invalid" for issue in issues) else "Unknown" if issues else "Decoded"
    return {
        "status": status, "replayable": not issues, "events": events if not issues else [],
        "unmodeled": any(issue["code"] in {"UNKNOWN_EVENT", "EVENT_UNMODELED", "PROJECTION_UNMODELED"} for issue in issues),
        "issues": issues, "model_status": "ASSUMED_MODEL", "projection": PROJECTION,
    }
