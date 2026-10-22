# StepSpan — Continuous Access Evidence Primitive

StepSpan converts published venue access information into evidence-bound decisions for directed route segments, then computes whether the submitted graph contains a continuous step-free route.

A page saying “a lift is available” does not prove that a visitor can reach it, exit it, or complete a visit. StepSpan preserves these gaps as UNKNOWN rather than turning a venue-wide statement into a positive route result.

## Contract interface

| Method | Purpose |
| --- | --- |
| `seal(plan_id, payload)` | Fix the venue, source URL, endpoints and graph in the sender's namespace. |
| `assess(plan_id, expected_revision)` | Fetch the source, reach consensus on edge findings, calculate paths, append an immutable review. |
| `get_plan(owner, plan_id)` | Read the immutable input and SHA-256 commitment. |
| `get_revision(owner, plan_id)` | Read the latest review number. |
| `get_review(owner, plan_id, revision)` | Read any historical source snapshot, findings and computed path. |
| `get_protocol()` | Return `stepspan-1`. |

Use 2–8 labeled nodes, 1–12 directed edges, and consecutive edge IDs E1 onward. Start and end must differ. Source URLs must be public HTTPS DNS URLs. The source must render to 100–60,000 characters.

```json
{"venue":"General Grant National Memorial · visitor center","url":"https://www.nps.gov/gegr/planyourvisit/accessibility.htm","nodes":[{"id":"sidewalk","label":"Riverside Drive sidewalk north of overlook pavilion"},{"id":"visitor_center","label":"Visitor center entrance via ramp"}],"edges":[{"id":"E1","from":"sidewalk","to":"visitor_center"}],"start":"sidewalk","end":"visitor_center"}
```

This is a live-source input example, not a preverified finding.

## Consensus and deterministic path calculation

The leader fetches and normalizes the published page and proposes PASS, BLOCKED or UNKNOWN for every edge. PASS and BLOCKED require a short, exact source quote. Missing or conditional access evidence produces UNKNOWN.

Each validator independently fetches the page. A changed normalized snapshot rejects the candidate. The validator independently classifies the edges, compares the exact ordered state vector, and checks whether each proposed quote supports the specific edge and direction. Quote audit answers require literal boolean `true`. Validators do not need identical prose or identical quote selection.

After acceptance, deterministic breadth-first search returns the shortest PASS-only path in declared edge order. If no supported path exists but a PASS/UNKNOWN path does, the result is UNRESOLVED. If every path in the submitted graph contains a BLOCKED edge, the result is BLOCKED. A structurally disconnected graph is UNRESOLVED. Cycles cannot cause infinite traversal. Reverse accessibility is never inferred.

The contract stores complete accepted source text, source digest, input digest, edge findings and route computation. Sender namespaces prevent another wallet from assessing or overwriting your plan. An expected revision guard prevents stale writes. Reassessment appends history; it does not overwrite previous snapshots. Reviews have ordinal revisions, not on-chain freshness guarantees.

## Run tests

```sh
python3 -m unittest discover -s tests -v
```

The suite exercises graph continuity, direction, alternate routes, stale revisions, immutable inputs, ownership, quote validation, source changes and independent disagreement. These protocol tests use a minimal mocked host. Additional SDK-backed checks use the pinned GenLayer runner and real SDK storage and calldata encoding, with mocked web and LLM responses. Neither suite establishes live-network consensus.

## Deploy and use

Import `contracts/stepspan.py` into GenLayer Studio, or deploy the exact bundled source from the companion application. Constructor arguments are empty. The app defaults to Stable Studionet, chain ID 61999, with normal full consensus (`leaderOnly: false`). No contract address or finalized transaction is included in this source package.

Call `seal` once with a new plan ID, await finality, then call `assess` with revision 0. Check successful finalized execution, majority agreement and public state readback. If a transaction fails or becomes undetermined, inspect the receipt before signing again. The implementation does not automatically retry writes or appeal.

## Boundaries

This is evidence inspection for a user-specified graph, not live navigation or a venue accessibility certification. A supported route is only supported by that source snapshot. It does not establish lift operation, wheelchair clearances, gradients or suitability for every person. BLOCKED is scoped to the submitted graph; it says nothing about unsubmitted alternatives.

URL syntax is constrained, but source ownership, DNS, redirects and retrieval availability remain trust boundaries. A user can choose an unofficial source; the contract does not certify publisher identity. The source is untrusted prompt data, and validators can still make correlated semantic errors. Dynamic pages may cause disagreement. A fresh assessment must be requested explicitly.

All plan inputs and fetched text are public. Use published venue pages, avoid personal information, and confirm current arrangements directly with the venue.

MIT licensed. GenLayer APIs: https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle

## SDK checks

Requires Python 3.12+ and the optional development dependencies:

```sh
pip install -r requirements-dev.txt
genvm-lint check contracts/stepspan.py
genvm-lint schema contracts/stepspan.py
python sdk-tests/test_sdk.py
```

The SDK tests cover persistent storage, calldata serialization, independent validator acceptance and rejection, source snapshot changes, ownership, immutable plans and historical revisions. Each check runs in a separate interpreter because the SDK registers one contract class per interpreter. The test framework may download its SDK release archive on first use. A newer runner advisory does not change the dependency pinned in the contract header.

The complete six-method ABI is also included in `schema.json`.
