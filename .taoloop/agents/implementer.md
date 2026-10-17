---
name: taoloop_implementer
role: implementer
description: Changes tracks/main/solution.py (and harness code when needed) so the new tests pass and the local energy_arbitrage score improves.
---

# Implementer: Apex (SN1) energy_arbitrage

**Entry criteria**
- A hypothesis from the coordinator and tests from the test_author exist.

**Inputs**
- `tracks/main/solution.py` (the candidate, the single uploaded file), `tracks/main/miner.py`
  and `AGENTS.md`.

**Work**
- Keep `solution.py` self-contained. Import only stdlib math helpers, `numpy`, `scipy` and
  `competition.energy_arbitrage.python.*`. Define a top-level `policy(view, state)`.
- Never read hidden state, files, the environment, processes or the network, and don't
  introspect the caller. The static rules in `miner.py` and the evaluator sandbox both enforce this.
- Keep the final flow-feasibility pass and the bounds clamp. Keep step-0 planning on CAPSTONE
  well under 30 s.
- Do not edit `tracks/main/vendor/`, which is the scorer.

**Test commands**
- `python3 tracks/main/miner.py check`
- `python3 tracks/main/miner.py evaluate`
- `EA_SEED=9001 EA_NUM_INSTANCES=10 python3 tracks/main/miner.py evaluate`

**Artifacts**
- The code change and the before and after `evaluate` JSON lines for both seeds.

**Exit criteria**
- `check` passes, the new tests pass and the score does not regress on either seed. If the
  hypothesis fails, revert it and report the numbers.
