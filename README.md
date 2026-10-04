# C1 synthetic review demo v1.2

Published synthetic review demo. Use it to inspect exact state checks on small fixtures and the separate decoder outcomes for unconfirmed coverage and malformed input. Version 1.2 updates publication documentation and packaging checks; the eight engine modules and synthetic inputs are unchanged from v1.1. Author-controlled material is licensed under GPL-2.0-or-later as identified in `LICENSE_NOTICE.md` and `LICENSE_MAP.json`.

This self-contained, standard-library Python package demonstrates four fixed synthetic examples. Eight engine modules are retained as byte-identical copies, with their source pins recorded in `SOURCE_PROVENANCE.json`. No real RPC responses, anchor evidence, acquisition indexes, addresses, or historical run records are included. The supplied fictitious identifiers are generated solely for the fixtures. This demo does not accept a real dataset or a network endpoint.

## Run

Use the [fixed v1.2 ZIP and SHA-256 checksum](https://github.com/akatsukiwork0320/c1-synthetic-review-demo/tree/distribution-v1.2), or download the repository source. The preserved [v1.1 archive](https://github.com/akatsukiwork0320/c1-synthetic-review-demo/tree/9dc29ba41194c7e9900c0dcae0b03ce47a993f11) remains unchanged; its preparation-time HOLD labels are historical, not the current publication status. The fixed distribution ZIP and GitHub-generated source ZIP are different archives.

Extract into a new directory. With Python 3.12.6, from that directory:

```text
python -I -B run_demo.py --output ../demo_run1_2
python -I -B run_checks.py --output ../demo_checks1_2.json
```

Both destinations must be new. Existing output is never overwritten. The runtime uses only the Python standard library, including SQLite; no package installation is needed. Python 3.12.6 is the tested version, not a claim of a tested version range.

`RESULT.json`, per-case checks, environment information, and the synthetic inputs are written into the chosen output directory. A test PASS means that the observed outcome matches the expected outcome; an expected Unknown or Invalid is a passing demonstration.

| Case | Path exercised | Expected native result | Meaning |
|---|---|---|---|
| D1 | ABI decoder, replay wrapper, SQLite state, final invariant checks | Known | Synthetic Mint, Burn, Swap and Flash leave the expected CORE/TICKS state. |
| D2 | Transaction decoder boundary | Unknown | Transaction coverage is explicitly unconfirmed; no replayable events are returned. This does not detect a secretly omitted record. |
| D3 | Transaction decoder boundary | Invalid | A valid log followed by malformed ABI data in the same transaction yields no partial replayable events. |
| D4 | ABI decoder, replay wrapper, SQLite state, final invariant checks | Known | A zero-valued Collect with equal endpoints is accepted and leaves CORE/TICKS unchanged. |

D2 and D3 stop at the decoder boundary, without invoking the replay wrapper. They are not end-to-end missing-history recovery tests. D4 concerns Collect's event-level treatment and does not generalize to Mint/Burn endpoint validity.

## What is checked

Expected values are separately handwritten for the small fixtures. The synthetic tick spacing is 60, with the liquidity range bounded by ticks -60 and +60. The terminal tick rows and core state are compared exactly for D1/D4. All fourteen named final invariant observations must be present, integer-valued, and zero. The issue code and empty event list are checked for D2/D3. `EXPECTED.json` gives the complete selected expectations. This is not an independent implementation of all AMM semantics: fixture construction and the production decoder share event signatures and specification conventions.

Each case runs in a fresh child process with the copied production guard installed, without a mocked hook. The parent checks input/code hashes, output bounds, and the observed guard counters. The guard observes only that Python process after hook installation; it is not an OS sandbox, a device-wide traffic monitor, or a guarantee about native-library I/O. Imports occur before the hook. The runner intentionally launches these children.

`LIMITS.json` defines a per-child timeout and fixed small fixture/output bounds. File count/size bounds are checked around execution, not enforced as OS quotas. This small demo does not establish an OOM-prevention theorem or production-scale complexity bound.

Known remains conditional on the synthetic model/evidence premises: ASSUMED_MODEL, source identity UNKNOWN, and MATHEMATICAL_INTEGRITY scope. The package does not independently compare a real terminal state, certify deployed bytecode, prove complete acquisition, verify token balances, or demonstrate transaction safety.

## Evidence and packaging

- `SOURCE_PROVENANCE.json`: source pins for the eight unchanged runtime copies and two synthetic test references.
- `RUNTIME_MANIFEST.json`: runtime file pins. Hash agreement is integrity checking, not an authenticated signature.
- `CHECKS.json`: the harness test results and actual executed test count, bound to runtime and test-driver hashes.
- `CLEAN_RUN.json`: an allowlisted copy executed outside the source directory with isolated Python import mode, using the same local Python installation. Both the four cases and the new harness tests are run.
- `MANIFEST.sha256`: every portable payload file; final ZIP additionally includes this manifest.
- Adjacent delivery/verification records: final archive hashes and the final ZIP's extracted execution, respectively. The extracted-run record is `synthetic_review_demo_v1_2.VERIFICATION.json`.

With the original adjacent ZIP and delivery record available, `python -B package_demo.py verify` checks the package. In an extracted directory that lacks those adjacent files, use the demo/test commands above. `package_demo.py build` can create a new local archive beside a complete folder before a manifest/archive exists; it refuses overwriting a sealed package. `stage` is only a development snapshot operation.

Packaging includes only explicitly allowlisted files. The working folder is not itself a sharing bundle. Candidate-management and publication-selection records, including adjacent delivery and verification records, stay outside the ZIP. This repository and its fixed synthetic archive are public. Private acquisition artifacts and correspondence are not part of the release. `PUBLIC_RELEASE` in the package metadata describes the release class; it is not a cryptographic proof of upload or an additional licence term.

## Authorship and licence status

The author supplied the research direction and approved AI-use disclosure. ChatGPT/Codex generated this harness and documentation with AI-assisted code review; this is not a human independent audit. These records do not assert author verification of every calculation.

See `LICENSE_NOTICE.md`, `LICENSE_MAP.json`, `THIRD_PARTY_NOTICES.md`, and `LICENSE_STATUS.json`. The author-controlled code, fixtures, tests, documentation, and metadata are licensed under GPL-2.0-or-later as mapped there. The eight engine files remain unchanged; the external licence notice records the author election without modifying their bytes. Existing upstream grants, source comments, and SPDX notices are retained. `LICENSES/GPL-2.0.txt` is the FSF licence document, retained under its own verbatim-copy permission rather than relicensed as authored source code.

The two included upstream Solidity files and the GPL text were obtained on 2026-10-03 and are pinned in `PUBLIC_SOURCE_PINS.json`; this release uses those retained copies. Neither Solidity file is executed by the demo. The licence election is complete for the identified author-controlled scope. It does not imply publication approval, independent legal clearance, or the scientific guarantees excluded above.
