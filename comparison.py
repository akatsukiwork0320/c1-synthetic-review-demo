# SPDX-License-Identifier: GPL-2.0-or-later
# Author-controlled contributions: Satoshi Kawasaki; see LICENSE_NOTICE.md.
# Adapted for the synthetic review demo revision on 2026-10-03.
"""Typed expected-subset comparison. A negative result is not a test failure by itself."""
OBSERVATION_IDS = frozenset((
    'BITMAP_TICKS_SYMMETRIC_DIFFERENCE', 'CURRENT_TICK_PREFIX_MISMATCH',
    'DUPLICATE_BITMAP_OR_TICK_REQUESTS', 'ENDPOINT_CLOSING_VIOLATIONS',
    'ENDPOINT_PARITY_VIOLATIONS', 'EXACT_TICKMATH_BOUNDARY_VIOLATIONS',
    'GROSS_NET_RANGE_VIOLATIONS', 'INITIALIZED_GROSS_CONTRADICTIONS',
    'MAX_LIQUIDITY_PER_TICK_VIOLATIONS', 'MISSING_BITMAP_WORDS',
    'NEGATIVE_OR_OVERFLOW_PREFIXES', 'NET_TOTAL_NONZERO',
    'OUT_OF_DOMAIN_BITMAP_BITS', 'SPACING_VIOLATIONS',
))

def compare(expected, actual, path=''):
    failures = []
    if type(expected) is not type(actual):
        return [path + ':TYPE']
    if isinstance(expected, dict):
        for key, value in expected.items():
            here = path + '/' + key
            if key not in actual:
                failures.append(here + ':MISSING')
            else:
                failures.extend(compare(value, actual[key], here))
    elif isinstance(expected, list):
        if len(expected) != len(actual):
            return [path + ':LENGTH']
        for i, (left, right) in enumerate(zip(expected, actual)):
            failures.extend(compare(left, right, path + '/' + str(i)))
    elif expected != actual:
        failures.append(path + ':VALUE')
    return failures


def wrapper_checks(actual):
    required = {'source_class': 'SYNTHETIC_FIXTURE', 'model': 'ASSUMED_MODEL',
                'source_identity': 'UNKNOWN', 'verification_scope': 'MATHEMATICAL_INTEGRITY'}
    failures = compare(required, actual)
    observations = actual.get('invariant_observations')
    if type(observations) is not dict or set(observations) != OBSERVATION_IDS or any(type(v) is not int or v != 0 for v in observations.values()):
        failures.append('/invariant_observations:EXPECTED_FIXED_IDS_AND_INTEGER_ZEROS')
    return failures
