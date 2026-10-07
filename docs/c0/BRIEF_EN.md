# Evidence-bound verification for Uniswap v3 pool-state replays

Satoshi Kawasaki | Individual researcher | Research & Implementation

**Submitted to Uniswap Foundation on 7 October 2026. Funding approval and contract terms are not confirmed.**

[Submitted one-page proposal (PDF)](C0_Application_Brief_EN.pdf) | [Existing fixed synthetic demo](https://github.com/akatsukiwork0320/c1-synthetic-review-demo/tree/cefb0b0fde950e6bf892554d4d99a2aed055fc63)

## The review problem

Maintainers of Uniswap v3 replay and indexing tools need to trace a comparison to its inputs, code and checks. Matching state values does not establish complete event history; a rejected test may have failed for an unrelated reason. The proposed workflow connects each in-scope claim to its evidence and unresolved assumptions.

## Inspect the existing baseline

C1 reconstructs selected v3 price, tick and liquidity state. The public demo has four synthetic cases covering ordinary updates, zero-valued Collect, explicitly unconfirmed coverage and malformed ABI. It runs with Python 3.12.6 and the standard library, without an RPC endpoint or wallet; use new output paths as described in the fixed demo README.

Unknown and Invalid cases stop before replay. They do not discover secretly omitted logs, and the Python process guard is not an OS sandbox. The separate private empirical case covers one pool and is not publicly reproducible evidence. Meta-audit integration is partial.

## The remaining work

A08, A17 and A22 remain incomplete: expected-result protection across registered comparison workers, reason/event-specific controls for checker explanations, and execution-evidence binding for the original claim register. C01-C07 remain OPEN. The grant proposal requests funding for completion and a public synthetic reference release; it does not bill completed C0/C1 work or application preparation.

## Proposed milestones and itemized request

**USD 46,000; estimated 500 person-hours over 28 weeks at 20 project hours per week, from an agreed start.** Scheduling margin is not additional billed labor.

| Milestone | Weeks | Hours | Labor USD | Direct allowance USD | Total USD |
|---|---|---:|---:|---:|---:|
| M1 Protected comparison execution | 1-6 | 112 | 10,080 | 400 | 10,480 |
| M2 Reason and event attribution controls | 7-12 | 104 | 9,360 | 200 | 9,560 |
| M3 Execution-bound claim review | 13-23 | 196 | 17,640 | 200 | 17,840 |
| M4 Reproducible reference release | 24-28 | 88 | 7,920 | 200 | 8,120 |
| Total | 1-28 | 500 | 45,000 | 1,000 | 46,000 |

- **M1:** Every registered target needs allowed-input/output, denied expected-result access, protected-write and prohibited-network controls. Oracle generation and grading remain outside tested workers; a dedicated probe alone is insufficient.
- **M2:** A valid baseline and every original semantic mutant type must reach the intended check, with correct reason/event attribution and mandatory-count controls. Include normal/abnormal rejection controls. Unrelated decoder errors, timeouts and input-hash rejection do not count as semantic detection.
- **M3:** Evaluate every registered claim, witness and interface against retrievable same-scope execution evidence. Distinguish missing, mismatched, diagnostic, changed and directly refuting evidence. All registered observable checks must be implemented and executed; missing in-scope work does not meet acceptance. Seven supported claims are not required.
- **M4:** Reproduce the releasable synthetic package in registered clean environments. Deliver source, tests, expected outcomes, dependency/licence inventory and a limitations report, keeping public reproduction distinct from restricted empirical evidence.

The proposed author compensation is 500 hours at USD 90, plus incremental AI/tool allowances of USD 800 and clean-environment compute allowances of USD 200. These are planning assumptions, not verified market rates or vendor quotations. Monthly progress preparation and quarterly review work are included. No independent human audit is secured or budgeted; existing subscriptions must not be billed twice.

The static low/base/high effort scenarios are 288/500/808 hours, not confidence intervals. The 28-week candidate covers the base case. The final worker/resource matrix, experiment contexts, schedule and private-evidence acceptance must be agreed before commitment; exceeding the base case requires a revised feasibility decision. Payment timing, licences, acceptance remediation and bounded support terms are not yet agreed.

## Public benefit and limits

The intended benefit is reusable verification material for v3 tooling maintainers and reviewers. The workflow complements v3-core tests, Foundry invariant testing and state-comparison tools such as Tycho. This initial comparison is not an exhaustive novelty finding. Adoption, review-time reduction and performance superiority have not been established.

The proposed implementation uses the existing Linux/WSL isolation path with registered environments. It does not promise OS isolation across every platform, arbitrary v4 hooks, trading, hosted operations or general EVM execution. Known remains conditional on declared model and evidence premises. Restricted evidence will not be published or replaced by synthetic evidence for empirical claims.

## Authorship and version status

Satoshi Kawasaki is the sole applicant and is responsible for the research questions, scope, acceptance criteria, result review and claims. Generative AI substantially supports implementation, documentation and review. AI-assisted review is not independent human auditing. No company development team is committed; technical mentorship is requested.

The linked application PDF is byte-identical to the submitted attachment. This overview expands its budget and acceptance details using the submitted form. The [old inquiry PDF](C0_Reviewable_V3_Brief_DRAFT.pdf) and [pre-application documentation](https://github.com/akatsukiwork0320/c1-synthetic-review-demo/tree/51e520a58a97c66fc6957794831859e2c64b71ab) remain historical references. The existing demo code, tests, licence notices and MANIFEST are unchanged. New-deliverable dependency and rights review remains pending; terms will be agreed before funded work starts.
