# Review Uniswap v3 results with traceable evidence

Developer-tooling research proposal | Satoshi Kawasaki

*Research proposal draft; not a grant award or completed-work report.*

Help developers and reviewers establish what a pool-state replay checked, which inputs and code version it covers, and what remains unverified.

## The review task

When an indexer or replay implementation changes, a colleague needs enough context to assess its result. Matching numbers alone do not establish complete input history. The goal is to attach scope, supporting evidence and unresolved dependencies to each reviewable claim.

## Inspect today: a working v3 baseline

C1 reconstructs selected v3 price, tick and liquidity state, with a single-pool empirical case. Its public demo runs four small synthetic cases. Meta-audit integration is partial and covers selected saved synthetic records; end-to-end evidence binding remains incomplete.

[Open the fixed public demo and README](https://github.com/akatsukiwork0320/c1-synthetic-review-demo/tree/cefb0b0fde950e6bf892554d4d99a2aed055fc63)

| Existing case | Expected result |
|---|---|
| Ordinary events / zero-valued Collect | Known selected state |
| Explicitly unconfirmed coverage | Unknown; no replayable output |
| Malformed ABI in one transaction | Invalid; no partial event output |

Python 3.12.6 + standard library; no package installation, RPC endpoint or wallet. Use a new output path. Unknown and Invalid cases stop before replay; they do not detect secretly omitted logs. The process guard is not an OS sandbox.

## Proposed grant: complete three evidence pathways

| Deliverable | Proposed acceptance evidence |
|---|---|
| Controlled comparison workers | Registered workers with isolation settings and allowed/denied resource controls. |
| Event-specific explanations | Analyzer-produced attribution for fixed omission tests, including wrong-event controls. |
| Traceable claim review | Each in-scope claim bound to witnesses, dependencies, inputs, code and an acceptance rule. |

## Why a rejected test is not enough

Planned illustration, not an executed meta-audit demo: with normal and premise controls passing, rejection for the expected reason and event supports the declared check; an unrelated decoder error does not. Worker failure leaves the claim unevaluated.

Deliverables are reference code, fixed tests and a reproducible report within an agreed v3 scope. Unsupported or unevaluated claims remain explicit. Budget, duration and support terms follow scope agreement.

**Would this scope fit your research or developer-tooling grants?**

## Scope and authorship

Selected v3 pool/tick state only. Input completeness and model identity remain explicit premises. No arbitrary EVM execution, v4 hooks, hosted service or trading-safety guarantee is proposed. Review-time savings and adoption are not yet measured.

Generative AI substantially assisted implementation and writing. Satoshi Kawasaki is responsible for the claims; AI review is not an independent human audit.
