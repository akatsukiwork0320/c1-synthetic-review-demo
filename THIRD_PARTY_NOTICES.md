# Source and licence notices

The author has elected GPL-2.0-or-later for the author-controlled material and contributions identified in `LICENSE_NOTICE.md` and `LICENSE_MAP.json`. Existing third-party grants and notices remain applicable. `LICENSE_STATUS.json` records the authorized `PUBLIC_RELEASE` classification. This synthetic demo is public; private research records are excluded. The unchanged v1.1 archive retains its preparation-time labels, which do not restrict recipients' GPL rights.

## Selected engine copies

Eight Python files in `engine/` are retained without changes. Their source pins and the pins of two synthetic-test references are in `SOURCE_PROVENANCE.json`. Source comments, including SPDX notices, were retained. The top-level election and per-file licence map record the author-controlled scope without adding headers or modifying these eight files.

| Files | Provenance and handling |
|---|---|
| `engine/ref_invariants.py` | Carries SPDX GPL-2.0-or-later. Its forward TickMath constants and integer-rounding calculation derive from Uniswap v3 TickMath; its inverse uses binary search. Preserve the upstream source and GPL terms. |
| `engine/reference_abi.py` | Refers to the Uniswap v3 pool event interface, Solidity ABI conventions and Keccak specification. Its author-controlled contributions are included in the GPL-2.0-or-later election; upstream grants and attribution remain applicable. The copied file is unchanged. |
| `engine/replay.py`, `engine/event_decoder.py`, `engine/replay_store.py`, `engine/tick_index.py`, `engine/support.py`, `engine/process_guard.py` | Unchanged implementation copies. Their author-controlled contributions are included in the GPL-2.0-or-later election recorded outside the files. |

The synthetic tests used as references are not copied as files. Fixture event topic constants were obtained from the selected reference ABI module during preparation. The demo is not an independent ABI-specification audit and does not claim that no original Python module was imported during preparation.

## Included upstream source

Uniswap v3-core commit `e3589b192d0be27e100cd0daaf6c97204fdb1899`:

- `upstream/TickMath.sol`: unchanged copy of `contracts/libraries/TickMath.sol`, SPDX GPL-2.0-or-later.
- `upstream/IUniswapV3PoolEvents.sol`: unchanged copy of `contracts/interfaces/pool/IUniswapV3PoolEvents.sol`, SPDX GPL-2.0-or-later.

The copies retain their original headers, comments, and existing upstream GPL-2.0-or-later grants. Neither Solidity file is executed by this Python demo. `LICENSES/GPL-2.0.txt` is the complete GNU GPL version 2 text obtained from the GNU project; the upstream SPDX expression permits version 2 or later. These three public reference files were obtained on 2026-10-03. `PUBLIC_SOURCE_PINS.json` records their exact public source URLs and SHA-256 hashes; this candidate uses those retained copies without a new download.

The FSF copyright and verbatim-copy permission in `LICENSES/GPL-2.0.txt` apply to the licence document itself. That document is retained unchanged and is excluded from any author election purporting to license authored software or other new material. Including licence text alone would not grant a licence to newly authored files; the explicit election and file map provide that scope.

The full `UniswapV3Pool.sol` reference bearing a BUSL-1.1 marker is **not included**. Its exclusion is a scope decision, not a claim that its present licence can be determined from the SPDX marker alone. The pinned repository's BUSL terms also specify a Change Date and Change License, which require separate consideration for any future inclusion. This package does not contain a legal opinion.

## New and adapted material

The fixture builder, selected expected results, comparison logic, worker, runner, tests, clean-copy verification, packaging, and documents were created/adapted for this demo on 2026-10-03. The fixture structure draws on the two synthetic tests identified by provenance. The runtime engine itself was not edited. New material was generated with ChatGPT/Codex and AI-assisted review under the author's direction. This statement is not a human independent audit.

The author's GPL-2.0-or-later election includes the identified author-controlled code, fixtures, expected results, tests, verification and packaging tools, documentation, and metadata. The exact file-level scope is in `LICENSE_MAP.json`. The corresponding source, GPL text, and third-party notices are retained for GPL-covered parts. The election is complete for that scope; it does not imply independent legal clearance, publication approval, or an operational support commitment. Packaging follows an explicit file allowlist. Candidate-management manifests, publication-selection records, and adjacent delivery/verification records remain outside the ZIP.
