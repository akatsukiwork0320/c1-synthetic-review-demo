"""Strict static ABI decoding for the nine pinned Uniswap v3 pool events.

Definitions: Uniswap/v3-core commit e3589b192d0be27e100cd0daaf6c97204fdb1899,
contracts/interfaces/pool/IUniswapV3PoolEvents.sol.  Integer/address encodings
follow https://docs.soliditylang.org/en/latest/abi-spec.html .  This decoder
checks representation, not contract execution or authenticity of a log.
"""
from __future__ import annotations

import re


class ABIError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class UnknownEvent(ABIError):
    def __init__(self, code: str = "UNKNOWN_EVENT"):
        super().__init__(code)


_MASK64 = (1 << 64) - 1
_ROUND_CONSTANTS = (
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
)
_ROTATION = (
    0, 1, 62, 28, 27,
    36, 44, 6, 55, 20,
    3, 10, 43, 25, 39,
    41, 45, 15, 21, 8,
    18, 2, 61, 56, 14,
)


def _rotate(value: int, amount: int) -> int:
    return ((value << amount) | (value >> ((64 - amount) % 64))) & _MASK64


def _permutation(state: list[int]) -> None:
    # Coordinates are x + 5*y.  This is Keccak-f[1600], 24 rounds.
    for constant in _ROUND_CONSTANTS:
        columns = [state[x] ^ state[x + 5] ^ state[x + 10] ^ state[x + 15] ^ state[x + 20] for x in range(5)]
        differences = [columns[(x - 1) % 5] ^ _rotate(columns[(x + 1) % 5], 1) for x in range(5)]
        for y in range(5):
            for x in range(5):
                state[x + 5 * y] ^= differences[x]
        moved = [0] * 25
        for y in range(5):
            for x in range(5):
                moved[y + 5 * ((2 * x + 3 * y) % 5)] = _rotate(state[x + 5 * y], _ROTATION[x + 5 * y])
        for y in range(5):
            for x in range(5):
                state[x + 5 * y] = (
                    moved[x + 5 * y]
                    ^ ((~moved[(x + 1) % 5 + 5 * y]) & moved[(x + 2) % 5 + 5 * y])
                ) & _MASK64
        state[0] ^= constant


def keccak256(data: bytes) -> bytes:
    """Ethereum Keccak-256, rate 1088/capacity 512, suffix 0x01 (not SHA3).

    The Keccak team's summary specifies the permutation and sponge:
    https://keccak.team/keccak_specs_summary.html .  XKCP's --ethereum mode
    likewise selects rate=1088, capacity=512, output=256 and suffix=0x01.
    Input is streamed through fixed-size internal blocks without copying it.
    """
    if type(data) is not bytes:
        raise TypeError("keccak256 requires bytes")
    rate = 136
    state = [0] * 25
    view = memoryview(data)
    complete = len(data) - len(data) % rate
    for offset in range(0, complete, rate):
        for lane in range(rate // 8):
            start = offset + lane * 8
            state[lane] ^= int.from_bytes(view[start:start + 8], "little")
        _permutation(state)
    tail = bytearray(rate)
    remaining = len(data) - complete
    tail[:remaining] = view[complete:]
    tail[remaining] ^= 0x01
    tail[-1] ^= 0x80
    for lane in range(rate // 8):
        state[lane] ^= int.from_bytes(tail[lane * 8:lane * 8 + 8], "little")
    _permutation(state)
    return b"".join(state[lane].to_bytes(8, "little") for lane in range(4))


_FIELDS = {
    "Initialize": (("sqrtPriceX96", "uint160", False), ("tick", "int24", False)),
    "Mint": (
        ("sender", "address", False), ("owner", "address", True),
        ("tickLower", "int24", True), ("tickUpper", "int24", True),
        ("amount", "uint128", False), ("amount0", "uint256", False), ("amount1", "uint256", False),
    ),
    "Collect": (
        ("owner", "address", True), ("recipient", "address", False),
        ("tickLower", "int24", True), ("tickUpper", "int24", True),
        ("amount0", "uint128", False), ("amount1", "uint128", False),
    ),
    "Burn": (
        ("owner", "address", True), ("tickLower", "int24", True), ("tickUpper", "int24", True),
        ("amount", "uint128", False), ("amount0", "uint256", False), ("amount1", "uint256", False),
    ),
    "Swap": (
        ("sender", "address", True), ("recipient", "address", True),
        ("amount0", "int256", False), ("amount1", "int256", False),
        ("sqrtPriceX96", "uint160", False), ("liquidity", "uint128", False), ("tick", "int24", False),
    ),
    "Flash": (
        ("sender", "address", True), ("recipient", "address", True),
        ("amount0", "uint256", False), ("amount1", "uint256", False),
        ("paid0", "uint256", False), ("paid1", "uint256", False),
    ),
    "IncreaseObservationCardinalityNext": (
        ("observationCardinalityNextOld", "uint16", False),
        ("observationCardinalityNextNew", "uint16", False),
    ),
    "SetFeeProtocol": (
        ("feeProtocol0Old", "uint8", False), ("feeProtocol1Old", "uint8", False),
        ("feeProtocol0New", "uint8", False), ("feeProtocol1New", "uint8", False),
    ),
    "CollectProtocol": (
        ("sender", "address", True), ("recipient", "address", True),
        ("amount0", "uint128", False), ("amount1", "uint128", False),
    ),
}

EVENTS = {}
for _name, _fields in _FIELDS.items():
    _signature = _name + "(" + ",".join(field[1] for field in _fields) + ")"
    EVENTS[_name] = {"signature": _signature, "topic0": "0x" + keccak256(_signature.encode("ascii")).hex(), "fields": _fields}
_BY_TOPIC = {spec["topic0"]: name for name, spec in EVENTS.items()}

_ENVELOPE_FIELDS = {
    "address", "topics", "data", "blockNumber", "blockHash", "transactionHash",
    "transactionIndex", "logIndex", "removed",
}
_HEX = re.compile(r"[0-9a-fA-F]*")
_QUANTITY = re.compile(r"0x(?:0|[1-9a-f][0-9a-f]*)")


def _hex_data(value, byte_count=None, max_bytes=None) -> str:
    if type(value) is not str or not value.startswith("0x"):
        raise ABIError("HEX_DATA")
    count = len(value) - 2
    if count % 2 or (byte_count is not None and count != 2 * byte_count):
        raise ABIError("HEX_WIDTH")
    if max_bytes is not None and count > 2 * max_bytes:
        raise ABIError("ABI_DATA_LIMIT")
    if _HEX.fullmatch(value[2:]) is None:
        raise ABIError("HEX_DATA")
    return value.lower()


def _quantity(value) -> int:
    if type(value) is not str or len(value) > 66 or _QUANTITY.fullmatch(value) is None:
        raise ABIError("RPC_QUANTITY")
    return int(value[2:], 16)


def decode_envelope(raw: dict) -> dict:
    """Validate metadata independently of whether topic0 is a known event.

    DATA/topics accept hex digit case; quantities require lowercase canonical
    uint256 quantities.  The return is JSON-serializable and does not mutate raw.
    """
    if type(raw) is not dict or set(raw) != _ENVELOPE_FIELDS:
        raise ABIError("LOG_SCHEMA")
    if type(raw["removed"]) is not bool:
        raise ABIError("LOG_SCHEMA")
    if type(raw["topics"]) is not list or not 1 <= len(raw["topics"]) <= 4:
        raise ABIError("TOPIC_COUNT")
    return {
        "address": _hex_data(raw["address"], byte_count=20),
        "block_number": _quantity(raw["blockNumber"]),
        "block_hash": _hex_data(raw["blockHash"], byte_count=32),
        "transaction_hash": _hex_data(raw["transactionHash"], byte_count=32),
        "transaction_index": _quantity(raw["transactionIndex"]),
        "log_index": _quantity(raw["logIndex"]),
        "removed": raw["removed"],
        "topics": [_hex_data(topic, byte_count=32) for topic in raw["topics"]],
        "data": _hex_data(raw["data"], max_bytes=8 * 32),
    }


def _decode_word(word: bytes, abi_type: str):
    unsigned = int.from_bytes(word, "big")
    if abi_type == "address":
        if unsigned >= 1 << 160:
            raise ABIError("ABI_ADDRESS_PADDING")
        return "0x" + word[12:].hex()
    if abi_type.startswith("uint"):
        bits = int(abi_type[4:])
        if unsigned >= 1 << bits:
            raise ABIError("ABI_UINT_PADDING")
        return unsigned
    bits = int(abi_type[3:])
    low = unsigned & ((1 << bits) - 1)
    signed = low - (1 << bits) if low & (1 << (bits - 1)) else low
    # Equality with canonical 256-bit two's complement catches both zero-
    # extended negatives and sign-extended positives for narrow signed types.
    if unsigned != signed % (1 << 256):
        raise ABIError("ABI_INT_PADDING")
    return signed


def decode_log(raw: dict) -> dict:
    envelope = decode_envelope(raw)
    topics = envelope.pop("topics")
    data = bytes.fromhex(envelope.pop("data")[2:])
    name = _BY_TOPIC.get(topics[0])
    if name is None:
        raise UnknownEvent()
    spec = EVENTS[name]
    indexed_count = sum(field[2] for field in spec["fields"])
    if len(topics) != indexed_count + 1:
        raise ABIError("TOPIC_COUNT")
    if len(data) != 32 * (len(spec["fields"]) - indexed_count):
        raise ABIError("ABI_DATA_LENGTH")
    topic_position, data_position = 1, 0
    fields = {}
    for field, abi_type, indexed in spec["fields"]:
        if indexed:
            word = bytes.fromhex(topics[topic_position][2:])
            topic_position += 1
        else:
            word = data[data_position:data_position + 32]
            data_position += 32
        fields[field] = _decode_word(word, abi_type)
    return {"kind": name, "fields": fields, **envelope}
