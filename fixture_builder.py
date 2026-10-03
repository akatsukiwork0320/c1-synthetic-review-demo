# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""Construct four small synthetic review fixtures without loading the engine.

Field layouts and integer words are hand-written. Event topic constants are
the published v3 signatures also used by the earlier synthetic tests; their
identity is shared reference material, not an independent ABI specification.
No saved acquisition data, network, private anchor, or wall clock is used.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ENGINE_MODULES = (
    "replay.py", "event_decoder.py", "reference_abi.py", "replay_store.py",
    "tick_index.py", "ref_invariants.py", "support.py", "process_guard.py",
)
CASE_IDS = ("D1", "D2", "D3", "D4")
TICK_SPACING = 60
PUBLIC_MAX_TICK = 887272


def synthetic_tick_capacity():
    """Public v3 bounds, aligned symmetrically; independent of any saved plan."""
    bound = (PUBLIC_MAX_TICK // TICK_SPACING) * TICK_SPACING
    count = 2 * (bound // TICK_SPACING) + 1
    return bound, count, ((1 << 128) - 1) // count

POOL = "0x" + "ab" * 20
OWNER = "0x" + "11" * 20
RECIPIENT = "0x" + "22" * 20
TOPICS = {
    "Mint": "0x7a53080ba414158be7ec69b987b5fb7d07dee101fe85488f0853ae16239d0bde",
    "Burn": "0x0c396cd989a39f4459b5fa1aed6a9a8dcdbc45908acfd67e028cd568da98982c",
    "Swap": "0xc42079f94a6350d7e6235f29174924f928cc2ac818eb64fed8004e115fbcca67",
    "Flash": "0xbdbdb71d7860376ba52b25a5028beea23581364a40522f6bcfb86bb1f2dca633",
    "Collect": "0x70935338e69775456a85ddef226c395fb668b63fa0115f5f20610b388e6ca9c0",
}
LIMITS = {
    "max_cases": 4,
    "max_fixture_files_per_case": 32,
    "max_file_bytes": 262144,
    "max_fixture_bytes_per_case": 1048576,
    "max_events_per_case": 5,
    "worker_timeout_seconds": 20,
    "seconds": 10,
    "output_bytes": 8388608,
    "body_bytes": 65536,
    "logs_per_response": 8,
    "source_metadata_rows": 16,
}


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def block_hash(number: int) -> str:
    """A synthetic identifier, not a computed block-header hash."""
    return "0x" + format(number, "064x")


def word(value: int | str) -> str:
    if type(value) is str:
        if len(value) != 42 or not value.startswith("0x"):
            raise ValueError("FIXTURE_ADDRESS")
        int(value[2:], 16)
        return value[2:].rjust(64, "0")
    if type(value) is not int or not -(1 << 255) <= value < (1 << 256):
        raise ValueError("FIXTURE_INTEGER")
    return format(value % (1 << 256), "064x")


def raw_log(kind: str, block: int, log_index: int) -> dict:
    layout = {
        "Mint": ([OWNER, -TICK_SPACING, TICK_SPACING], [RECIPIENT, 3, 3, 0]),
        "Burn": ([OWNER, -TICK_SPACING, TICK_SPACING], [1, 1, 0]),
        "Swap": ([OWNER, RECIPIENT], [1, -1, 1 << 96, 12, 0]),
        "Flash": ([OWNER, RECIPIENT], [1, 0, 1, 0]),
        # This no-effect case does not authorize these endpoints for Mint/Burn.
        "Collect": ([OWNER, 0, 0], [RECIPIENT, 0, 0]),
    }
    indexed, data = layout[kind]
    return {
        "address": POOL,
        "topics": [TOPICS[kind]] + ["0x" + word(value) for value in indexed],
        "data": "0x" + "".join(word(value) for value in data),
        "blockNumber": hex(block), "blockHash": block_hash(block),
        "transactionHash": block_hash(10000 + block),
        "transactionIndex": "0x0", "logIndex": hex(log_index), "removed": False,
    }


def _write_bytes(path: Path, raw: bytes) -> None:
    if len(raw) > LIMITS["max_file_bytes"]:
        raise ValueError("FIXTURE_FILE_LIMIT")
    with path.open("xb") as handle:
        handle.write(raw)


def _save(path: Path, value) -> None:
    _write_bytes(path, canonical(value) + b"\n")


def _rows(path: Path, values: list[dict]) -> None:
    _write_bytes(path, b"".join(canonical(value) + b"\n" for value in values))


def _pin(path: Path, base: Path) -> dict:
    raw = path.read_bytes()
    return {"path": path.relative_to(base).as_posix(), "bytes": len(raw), "sha256": digest(raw)}


def build_case(case_dir: Path, case_id: str, package_dir: Path) -> dict:
    """Create a NEW directory and return the same relative metadata as CASE.json.

    Existing directories (including empty ones) are refused. Engine bytes are
    copied from package_dir/engine and pinned as the actual runtime closure.
    No engine module is imported or executed while building a fixture.
    """
    if case_id not in CASE_IDS:
        raise ValueError("FIXTURE_CASE_ID")
    case_dir, package_dir = Path(case_dir), Path(package_dir)
    if case_dir.exists() or case_dir.is_symlink():
        raise FileExistsError("FIXTURE_OUTPUT_EXISTS")
    engine_source = package_dir / "engine"
    if not engine_source.is_dir() or engine_source.is_symlink():
        raise ValueError("ENGINE_DIRECTORY")
    code = {}
    for name in ENGINE_MODULES:
        source = engine_source / name
        if not source.is_file() or source.is_symlink():
            raise ValueError("ENGINE_SOURCE_FILE")
        if source.stat().st_size > LIMITS["max_file_bytes"]:
            raise ValueError("ENGINE_SOURCE_FILE_LIMIT")
        code[name] = source.read_bytes()
    if sum(map(len, code.values())) > LIMITS["max_fixture_bytes_per_case"] // 2:
        raise ValueError("ENGINE_SOURCE_TOTAL_LIMIT")
    case_dir.mkdir(exist_ok=False)
    unit = case_dir / "unit"
    unit.mkdir()
    engine = unit / "engine"
    engine.mkdir()
    for name, raw in code.items():
        _write_bytes(engine / name, raw)
    metadata = {
        "schema": "c1-synthetic-review-case/1", "case_id": case_id,
        "source_class": "SYNTHETIC_FIXTURE", "engine_dir": "unit/engine",
        "unit_dir": "unit", "output_dir": "out", "limits": dict(LIMITS),
        "code_pins": [_pin(engine / name, case_dir) for name in ENGINE_MODULES],
    }
    if case_id in ("D2", "D3"):
        logs = [raw_log("Swap", 101, 0)]
        if case_id == "D3":
            logs.append(raw_log("Swap", 101, 1))
            logs[1]["data"] = "0x"
        request = {
            "logs": logs,
            "arguments": {"pool": POOL, "tick_spacing": TICK_SPACING, "projection": "CORE_TICKS",
                          "complete": case_id == "D3", "max_logs": LIMITS["logs_per_response"]},
        }
        _save(case_dir / "DECODER_INPUT.json", request)
        metadata.update(layer="TRANSACTION_DECODER", decoder_input="DECODER_INPUT.json",
                        input_pin=_pin(case_dir / "DECODER_INPUT.json", case_dir),
                        event_count=len(logs))
    else:
        anchor_dir = case_dir / "anchor"
        anchor_dir.mkdir()
        # Public formula and a deliberately chosen synthetic spacing.
        _, _, max_liquidity = synthetic_tick_capacity()
        _save(anchor_dir / "ANCHOR_STATE.json", {"values": {
            "slot0": {"sqrtPriceX96": str(1 << 96), "tick": "0"},
            "tickSpacing": {"tickSpacing": str(TICK_SPACING)},
            "maxLiquidityPerTick": {"maxLiquidityPerTick": str(max_liquidity)},
            "liquidity": {"liquidity": "10"},
        }})
        _rows(anchor_dir / "TICKS.jsonl", [
            {"tick": str(-TICK_SPACING), "values": {"liquidityGross": "10", "liquidityNet": "10", "initialized": True}},
            {"tick": str(TICK_SPACING), "values": {"liquidityGross": "10", "liquidityNet": "-10", "initialized": True}},
        ])
        _rows(case_dir / "BRANCH.jsonl", [
            {"number": 101, "hash": block_hash(101), "parent_hash": block_hash(100)},
            {"number": 102, "hash": block_hash(102), "parent_hash": block_hash(101)},
        ])
        logs = [raw_log("Mint", 101, 0), raw_log("Burn", 101, 1),
                raw_log("Swap", 102, 0), raw_log("Flash", 102, 1)]
        if case_id == "D4":
            logs.append(raw_log("Collect", 102, 2))
        body = canonical({"jsonrpc": "2.0", "id": "fixture-1", "result": logs})
        if len(logs) > LIMITS["max_events_per_case"] or len(body) > LIMITS["body_bytes"]:
            raise ValueError("FIXTURE_BODY_LIMIT")
        _write_bytes(case_dir / "rpc_body.json", body)
        source = {"ordinal": 1, "body_path": "rpc_body.json", "offset": 0,
                  "body_bytes": len(body), "body_sha256": digest(body), "request_id": "fixture-1",
                  "from_block": 101, "to_block": 102}
        _rows(unit / "SOURCE_ROWS.jsonl", [source])
        artifacts = [_pin(path, case_dir) for path in (
            anchor_dir / "ANCHOR_STATE.json", anchor_dir / "TICKS.jsonl", case_dir / "BRANCH.jsonl")]
        binding = {
            "schema": "p5-input-bindings/1", "scope_id": "public-synthetic-" + case_id.lower(),
            "scope": {"anchor_block": 100, "anchor_hash": block_hash(100), "from_block": 101,
                      "to_block": 102, "target_pool_address": POOL},
            "artifacts": artifacts, "branch_index": artifacts[-1], "response_count": 1,
        }
        _save(unit / "INPUT_BINDINGS.json", binding)
        _save(unit / "P4_ACCEPTANCE.json", {
            "anchor_verified": True, "verification_scope": "MATHEMATICAL_INTEGRITY",
            "source_identity": "UNKNOWN", "model": "ASSUMED_MODEL", "source_class": "SYNTHETIC_FIXTURE",
        })
        plan = {
            "schema": "p5-run-plan/1", "scope_id": binding["scope_id"],
            "source_class": "SYNTHETIC_FIXTURE", "model": "ASSUMED_MODEL", "output": "out",
            "verification_scope": "MATHEMATICAL_INTEGRITY", "source_identity": "UNKNOWN",
            "code_pins": [_pin(engine / name, unit) for name in ENGINE_MODULES],
            "unit_pins": [_pin(unit / name, unit) for name in (
                "INPUT_BINDINGS.json", "P4_ACCEPTANCE.json", "SOURCE_ROWS.jsonl")],
            "limits": {name: LIMITS[name] for name in (
                "seconds", "output_bytes", "body_bytes", "logs_per_response", "source_metadata_rows")},
        }
        _save(unit / "RUN_PLAN.json", plan)
        _save(unit / "RUN_PLAN.SEAL.json", {"raw_sha256": digest((unit / "RUN_PLAN.json").read_bytes())})
        metadata.update(layer="REPLAY_WRAPPER", run_plan="unit/RUN_PLAN.json", event_count=len(logs))
    _save(case_dir / "CASE.json", metadata)
    files = [path for path in case_dir.rglob("*") if path.is_file()]
    if len(files) > LIMITS["max_fixture_files_per_case"]:
        raise ValueError("FIXTURE_FILE_COUNT_LIMIT")
    if sum(path.stat().st_size for path in files) > LIMITS["max_fixture_bytes_per_case"]:
        raise ValueError("FIXTURE_TOTAL_LIMIT")
    return metadata
