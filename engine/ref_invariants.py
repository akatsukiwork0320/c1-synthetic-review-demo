# SPDX-License-Identifier: GPL-2.0-or-later
"""Integer anchor invariants; no file, network, decoder, or solver access.

TickMath forward constants/rounding are translated from the pinned Uniswap
v3-core TickMath.sol, commit e3589b192d0be27e100cd0daaf6c97204fdb1899.
The inverse is an independent integer binary search over that forward map.

Input iterables must be nondecreasing (SQLite ORDER BY is sufficient). Only
the current row and a 256-bit word are kept: this module does not materialize
the bitmap/tick census. Duplicate keys are counted and only their first row
is used for the remaining checks; the duplicate condition cannot then pass.
All quantities are necessary reference-model constraints, not a proof of
actual position ownership, chain authenticity, or transaction reachability.
"""
from __future__ import annotations

MIN_TICK = -887272
MAX_TICK = 887272
MIN_SQRT_RATIO = 4295128739
MAX_SQRT_RATIO = 1461446703485210103287273052203988822378723970342
UINT128_MAX = (1 << 128) - 1
FACTORS = (
    0xfffcb933bd6fad37aa2d162d1a594001,
    0xfff97272373d413259a46990580e213a,
    0xfff2e50f5f656932ef12357cf3c7fdcc,
    0xffe5caca7e10e4e61c3624eaa0941cd0,
    0xffcb9843d60f6159c9db58835c926644,
    0xff973b41fa98c081472e6896dfb254c0,
    0xff2ea16466c96a3843ec78b326b52861,
    0xfe5dee046a99a2a811c461f1969c3053,
    0xfcbe86c7900a88aedcffc83b479aa3a4,
    0xf987a7253ac413176f2b074cf7815e54,
    0xf3392b0822b70005940c7a398e4b70f3,
    0xe7159475a2c29b7443b29c7fa6e889d9,
    0xd097f3bdfd2022b8845ad8f792aa5825,
    0xa9f746462d870fdf8a65dc1f90e061e5,
    0x70d869a156d2a1b890bb3df62baf32f7,
    0x31be135f97d08fd981231505542fcfa6,
    0x9aa508b5b7a84e1c677de54f3e99bc9,
    0x5d6af8dedb81196699c329225ee604,
    0x2216e584f5fa1ea926041bedfe98,
    0x48a170391f7dc42444e8fa2,
)
CENSUS_IDS = (
    "MISSING_BITMAP_WORDS", "DUPLICATE_BITMAP_OR_TICK_REQUESTS",
    "OUT_OF_DOMAIN_BITMAP_BITS", "BITMAP_TICKS_SYMMETRIC_DIFFERENCE",
    "INITIALIZED_GROSS_CONTRADICTIONS",
)
NUMERIC_IDS = (
    "GROSS_NET_RANGE_VIOLATIONS", "SPACING_VIOLATIONS",
    "MAX_LIQUIDITY_PER_TICK_VIOLATIONS", "ENDPOINT_PARITY_VIOLATIONS",
    "NEGATIVE_OR_OVERFLOW_PREFIXES", "NET_TOTAL_NONZERO",
    "CURRENT_TICK_PREFIX_MISMATCH", "ENDPOINT_CLOSING_VIOLATIONS",
    "EXACT_TICKMATH_BOUNDARY_VIOLATIONS",
)


def integer(value, name):
    if type(value) is not int:
        raise ValueError(name + "_requires_exact_integer")
    return value


def trunc_div(n: int, d: int) -> int:
    """Solidity signed integer division, without a float intermediate."""
    integer(n, "numerator")
    integer(d, "denominator")
    if d == 0:
        raise ValueError("zero_denominator")
    return (1 if (n < 0) == (d < 0) else -1) * (abs(n) // abs(d))


def sqrt_ratio_at_tick(tick: int) -> int:
    integer(tick, "tick")
    if not MIN_TICK <= tick <= MAX_TICK:
        raise ValueError("tick_out_of_range")
    absolute = abs(tick)
    ratio = 1 << 128
    for bit, factor in enumerate(FACTORS):
        if absolute & (1 << bit):
            ratio = (ratio * factor) >> 128
    if tick > 0:
        ratio = ((1 << 256) - 1) // ratio
    return (ratio >> 32) + int((ratio & ((1 << 32) - 1)) != 0)


def tick_at_sqrt_ratio(sqrt_price: int) -> int:
    integer(sqrt_price, "sqrt_price")
    if not MIN_SQRT_RATIO <= sqrt_price < MAX_SQRT_RATIO:
        raise ValueError("sqrt_price_out_of_range")
    lo, hi = MIN_TICK, MAX_TICK
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if sqrt_ratio_at_tick(mid) <= sqrt_price:
            lo = mid
        else:
            hi = mid
    return lo


def usable_tick_bounds(spacing: int) -> tuple[int, int]:
    integer(spacing, "spacing")
    if not 0 < spacing < (1 << 23):
        raise ValueError("spacing_out_of_range")
    return trunc_div(MIN_TICK, spacing) * spacing, trunc_div(MAX_TICK, spacing) * spacing


def max_liquidity_for_spacing(spacing: int) -> int:
    lo, hi = usable_tick_bounds(spacing)
    return UINT128_MAX // ((hi - lo) // spacing + 1)


def boundary_check(slot0: dict) -> dict:
    sqrt_price = integer(slot0["sqrtPriceX96"], "sqrtPriceX96")
    current_tick = integer(slot0["tick"], "stored_tick")
    good_domain = MIN_SQRT_RATIO <= sqrt_price < MAX_SQRT_RATIO and MIN_TICK <= current_tick <= MAX_TICK
    inverse = tick_at_sqrt_ratio(sqrt_price) if MIN_SQRT_RATIO <= sqrt_price < MAX_SQRT_RATIO else None
    exact = inverse is not None and sqrt_price == sqrt_ratio_at_tick(inverse)
    # An exact downward crossing stores inverse - 1; the boundary need not be initialized.
    matches = good_domain and (current_tick == inverse or (exact and current_tick == inverse - 1))
    return {"violations": int(not matches), "inverse_tick": inverse,
            "exact_tick_price": exact, "stored_tick": current_tick,
            "necessary_condition_only": True}


def evaluate_state(slot0: dict, liquidity: int, spacing: int,
                   max_liquidity_per_tick: int, bitmap_rows, tick_rows) -> dict:
    """Evaluate 5 census + 9 numeric observations using sorted one-pass rows.

    bitmap_rows: (signed word index, uint256 bitmap).
    tick_rows: (tick index, dict with liquidityGross/liquidityNet/initialized).
    Out-of-domain metric counts invalid set bits AND unexpected word requests
    (including zero words), with separate detail counters. Invalid spacing is
    reported and dependent checks are omitted instead of fabricated as zero.
    Type errors or descending iterables are evaluator failures, not state facts.
    """
    integer(liquidity, "liquidity")
    integer(spacing, "spacing")
    integer(max_liquidity_per_tick, "maxLiquidityPerTick")
    if not 0 <= liquidity <= UINT128_MAX:
        raise ValueError("liquidity_abi_range")
    boundary = boundary_check(slot0)
    observations = {"EXACT_TICKMATH_BOUNDARY_VIOLATIONS": boundary["violations"]}
    details = {"boundary": boundary, "dependent_checks_evaluated": False}
    if not 0 < spacing < (1 << 23):
        observations["SPACING_VIOLATIONS"] = 1
        return {"observations": observations, "details": details}

    observations.update({cid: 0 for cid in CENSUS_IDS + NUMERIC_IDS if cid not in observations})
    lo_tick, hi_tick = usable_tick_bounds(spacing)
    lo_word, hi_word = (lo_tick // spacing) >> 8, (hi_tick // spacing) >> 8
    derived_max = max_liquidity_for_spacing(spacing)
    observations["MAX_LIQUIDITY_PER_TICK_VIOLATIONS"] += int(max_liquidity_per_tick != derived_max)
    details.update({"expected_word_min": lo_word, "expected_word_max": hi_word,
                    "expected_word_count": hi_word - lo_word + 1,
                    "derived_max_liquidity_per_tick": derived_max,
                    "bitmap_rows": 0, "tick_rows": 0, "bitmap_unique_words": 0,
                    "unique_ticks": 0, "bitmap_initialized_ticks": 0,
                    "out_of_domain_set_bits": 0, "unexpected_bitmap_words": 0})

    def bitmap_ticks():
        previous = None
        cursor = lo_word
        for word, value in bitmap_rows:
            integer(word, "word")
            integer(value, "bitmap")
            if not -(1 << 15) <= word < (1 << 15) or not 0 <= value < (1 << 256):
                raise ValueError("bitmap_abi_range")
            details["bitmap_rows"] += 1
            if previous is not None and word < previous:
                raise ValueError("bitmap_rows_not_sorted")
            if word == previous:
                observations["DUPLICATE_BITMAP_OR_TICK_REQUESTS"] += 1
                continue
            previous = word
            details["bitmap_unique_words"] += 1
            if lo_word <= word <= hi_word:
                observations["MISSING_BITMAP_WORDS"] += max(0, word - cursor)
                cursor = word + 1
            else:
                details["unexpected_bitmap_words"] += 1
                observations["OUT_OF_DOMAIN_BITMAP_BITS"] += 1
            while value:
                bit_value = value & -value
                bit = bit_value.bit_length() - 1
                tick = (word * 256 + bit) * spacing
                value ^= bit_value
                if not MIN_TICK <= tick <= MAX_TICK:
                    details["out_of_domain_set_bits"] += 1
                    observations["OUT_OF_DOMAIN_BITMAP_BITS"] += 1
                else:
                    details["bitmap_initialized_ticks"] += 1
                    yield tick
        observations["MISSING_BITMAP_WORDS"] += max(0, hi_word + 1 - cursor)

    bitmap_iter = iter(bitmap_ticks())
    expected = next(bitmap_iter, None)
    previous_tick = None
    prefix = 0
    current_prefix = 0
    minimum_prefix = 0
    maximum_prefix = 0
    for tick, values in tick_rows:
        integer(tick, "tick")
        if type(values) is not dict:
            raise ValueError("tick_values_require_dict")
        gross = integer(values["liquidityGross"], "liquidityGross")
        net = integer(values["liquidityNet"], "liquidityNet")
        initialized = values["initialized"]
        if type(initialized) is not bool:
            raise ValueError("initialized_requires_bool")
        details["tick_rows"] += 1
        if previous_tick is not None and tick < previous_tick:
            raise ValueError("tick_rows_not_sorted")
        if tick == previous_tick:
            observations["DUPLICATE_BITMAP_OR_TICK_REQUESTS"] += 1
            continue
        previous_tick = tick
        details["unique_ticks"] += 1
        while expected is not None and expected < tick:
            observations["BITMAP_TICKS_SYMMETRIC_DIFFERENCE"] += 1
            expected = next(bitmap_iter, None)
        if expected == tick:
            expected = next(bitmap_iter, None)
        else:
            observations["BITMAP_TICKS_SYMMETRIC_DIFFERENCE"] += 1
        observations["INITIALIZED_GROSS_CONTRADICTIONS"] += int(not initialized or gross <= 0)
        observations["GROSS_NET_RANGE_VIOLATIONS"] += int(
            not 0 <= gross <= UINT128_MAX or not -(1 << 127) <= net < (1 << 127) or gross < abs(net))
        observations["SPACING_VIOLATIONS"] += int(not MIN_TICK <= tick <= MAX_TICK or tick % spacing != 0)
        observations["MAX_LIQUIDITY_PER_TICK_VIOLATIONS"] += int(gross > derived_max)
        parity_bad = (gross + net) % 2 != 0 or (gross - net) % 2 != 0
        observations["ENDPOINT_PARITY_VIOLATIONS"] += int(parity_bad)
        if parity_bad:
            # Integral opening/closing amounts are part of endpoint feasibility.
            observations["ENDPOINT_CLOSING_VIOLATIONS"] += 1
        else:
            opening, closing = (gross + net) // 2, (gross - net) // 2
            observations["ENDPOINT_CLOSING_VIOLATIONS"] += int(opening < 0 or closing < 0 or closing > prefix)
        prefix += net
        minimum_prefix = min(minimum_prefix, prefix)
        maximum_prefix = max(maximum_prefix, prefix)
        observations["NEGATIVE_OR_OVERFLOW_PREFIXES"] += int(not 0 <= prefix <= UINT128_MAX)
        if tick <= slot0["tick"]:
            current_prefix = prefix
    while expected is not None:
        observations["BITMAP_TICKS_SYMMETRIC_DIFFERENCE"] += 1
        expected = next(bitmap_iter, None)
    observations["NET_TOTAL_NONZERO"] = int(prefix != 0)
    observations["CURRENT_TICK_PREFIX_MISMATCH"] = int(current_prefix != liquidity)
    details.update({"dependent_checks_evaluated": True, "total_net": prefix,
                    "current_tick_prefix": current_prefix, "liquidity": liquidity,
                    "minimum_prefix": minimum_prefix, "maximum_prefix": maximum_prefix})
    return {"observations": observations, "details": details}
