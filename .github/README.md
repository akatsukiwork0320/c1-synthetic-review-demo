# Review a Uniswap v3 replay result and its evidence

**Research proposal and existing synthetic demo | Satoshi Kawasaki**

[Read the one-page proposal (PDF)](../docs/c0/C0_Reviewable_V3_Brief_DRAFT.pdf) | [Read the same brief as text](../docs/c0/BRIEF_EN.md)

The proposal describes future work; publication is not a grant application or an award.

For developers and reviewers checking reconstructed pool state, the research goal is to connect each result to its scope, inputs, code version and unresolved evidence. The current public demo exercises replay and ABI boundaries; complete meta-audit integration is proposed work.

## Run the existing four-case demo

Open the [fixed public v1.3 README](https://github.com/akatsukiwork0320/c1-synthetic-review-demo/tree/cefb0b0fde950e6bf892554d4d99a2aed055fc63), obtain the package and extract it into a new directory. From that directory, with Python 3.12.6:

```text
python -I -B run_demo.py --output ../demo_run1_3
```

The output path must not exist. No package installation, RPC endpoint or wallet is required. Open the generated `RESULT.json` and per-case results:

| Case | Expected outcome | What to inspect |
|---|---|---|
| D1 | Known | Exact selected CORE/TICKS state after ordinary synthetic events |
| D2 | Unknown | Explicitly unconfirmed coverage yields no replayable events |
| D3 | Invalid | Malformed ABI yields no partial transaction output |
| D4 | Known | Zero-valued Collect leaves selected state unchanged |

D2 does not discover a secretly omitted log. D2/D3 stop before replay. A test PASS means the expected outcome occurred, including expected Unknown or Invalid; it does not mean every state is Known.

To run the separate harness checks, use another new output path:

```text
python -I -B run_checks.py --output ../demo_checks1_3.json
```

These commands run in the existing package, not in this document folder. Its Python process guard is not an OS sandbox. Retain the source README, GPL-2.0-or-later notices and file-level provenance; this landing page does not replace them.

## What the proposed evidence review adds

A bounded v3 project would complete controlled worker execution, analyzer-produced attribution for fixed omission tests, and traceable claim-to-evidence links. Current integration is partial. Deliverables would be reference code, fixed tests and a reproducible report.

An additional synthetic receipt demo is **planned, not implemented or published**. Its first three examples would distinguish:

1. A check reached the intended rejection reason and event, with normal and premise controls passing.
2. Rejection happened for an unrelated reason, which does not support that check.
3. A synthetic receipt reports worker failure, leaving the claim unevaluated.

The full planned suite has eight receipt cases. These declared synthetic receipts do not audit live outputs of the existing replay demo. Actual runner errors must remain errors.

## Scope and authorship

The empirical replay case covers one pool. Known remains conditional on the model and evidence premises. This is not a general EVM simulator, a v4 hook verifier or a trading-safety guarantee. Review-time savings have not been measured.

Generative AI substantially assisted implementation and writing. Satoshi Kawasaki is responsible for the claims; AI review is not an independent human audit.

## Package documentation

The [original v1.3 package README](../README.md), [licence notice](../LICENSE_NOTICE.md) and [file-level provenance](../SOURCE_PROVENANCE.json) remain unchanged. This page and the C0 brief are additional documentation, outside the sealed v1.3 package manifest. For the exact tested package, use the fixed revision linked above.
