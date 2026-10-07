# Evidence-bound verification for Uniswap v3 replays

**Submitted research proposal and existing synthetic demo | Satoshi Kawasaki**

[Read the submitted one-page proposal (PDF)](../docs/c0/C0_Application_Brief_EN.pdf) | [Read the public proposal overview](../docs/c0/BRIEF_EN.md)

Submitted to Uniswap Foundation on 7 October 2026. Funding approval and contractual terms are not confirmed. The proposed new verification workflow is pre-launch; the existing synthetic replay demo is available below.

For developers and reviewers checking reconstructed pool state, the goal is to connect each in-scope result to its inputs, code version, comparison conditions and unresolved assumptions. Matching state values alone does not establish complete event history.

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

## Proposed work and acceptance evidence

The request is **USD 46,000 for an estimated 500 person-hours over 28 weeks at 20 project hours per week**, from an agreed start. Completed C0/C1 work and application preparation are excluded from the request.

| Proposed deliverable | Weeks | USD | Acceptance evidence |
|---|---|---:|---|
| M1 Protected comparison execution | 1-6 | 10,480 | Allowed/denied controls across every registered target; expected results and grading outside the worker. |
| M2 Reason and event attribution controls | 7-12 | 9,560 | Valid baseline, intended check reached, correct reason/event, and all original semantic controls. |
| M3 Execution-bound claim review | 13-23 | 17,840 | Seven claim reviews linked to retrievable same-scope execution evidence and unresolved dependencies. |
| M4 Reproducible reference release | 24-28 | 8,120 | Clean-environment synthetic reproduction; source, tests, dependency/licence records and report. |

The original A08, A17 and A22 acceptance items remain incomplete; claims C01-C07 remain OPEN. All registered observable checks must be implemented and executed. Every claim need not become supported, but missing in-scope implementation or execution does not meet acceptance. This documentation update does not add those capabilities to the four-case demo.

The final worker/resource matrix, experiment contexts, delivery schedule, licences and acceptance-remediation terms remain subject to agreement. The budget is a planning estimate, not a measured market rate or optimal-price claim. [Read the detailed scope and budget](../docs/c0/BRIEF_EN.md).

## Scope and authorship

The private empirical case covers one pool and is not publicly reproducible evidence. Known remains conditional on the model and evidence premises. This is not a general EVM simulator, arbitrary v4 hook verifier or trading-safety guarantee. Hosted operations are outside the proposed scope. Adoption and review-time savings have not been measured.

Satoshi Kawasaki applies as an individual, defines the research questions and acceptance criteria, reviews results, and takes responsibility for the claims and limitations. Generative AI substantially supports implementation, documentation and review. AI-assisted review is not independent human auditing. No company development team or independent human auditor is committed to the project.

## Package and version documentation

The [original v1.3 package README](../README.md), [licence notice](../LICENSE_NOTICE.md), [file-level provenance](../SOURCE_PROVENANCE.json) and sealed demo remain unchanged. The C0 documents are outside that package's MANIFEST and have their own [document checksums](../docs/c0/C0_FILES.sha256).

The new PDF is the same file attached to the formal application. The [earlier inquiry PDF](../docs/c0/C0_Reviewable_V3_Brief_DRAFT.pdf) remains available as historical material; its scope and questions should not be read as the current application. The [pre-application documentation revision](https://github.com/akatsukiwork0320/c1-synthetic-review-demo/tree/51e520a58a97c66fc6957794831859e2c64b71ab) is preserved. No award or technical acceptance closure is implied by this publication.
