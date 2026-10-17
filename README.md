# Apex (subnet 1) miner line

This is the shared starting point for mining **Apex**, Bittensor subnet 1 on finney, run by
Macrocosmos. Apex is a set of coding competitions. You submit a solution file, the Apex
orchestrator scores it in a sandbox, and only the best submission in each competition earns
emissions.

This line has one track, `tracks/main`, for the **energy_arbitrage** competition. The track holds
a battery-trading policy (`tracks/main/solution.py`) and a vendored copy of the upstream
evaluator, so you can score it locally before you pay to submit.

## Quick start

```bash
python3 -m pip install -r tracks/main/requirements.txt
python3 tracks/main/miner.py check       # must pass
python3 tracks/main/miner.py evaluate    # local score (higher is better, max 10)
python3 tracks/main/miner.py run         # packages the file and prints the submit command
```

With seed 123 and 5 instances, the shipped policy scores about 6.65 (pure-Python fallback, no
numpy). Upstream's example `energy_solver_2` scores about 1.21 on the same instances.

## Submitting

TaoLoop handles setup: it installs the Apex CLI, links the registered hotkey with
`apex link`, finds the energy_arbitrage competition id and packages the candidate. The one step
that is yours is approving the fee:

```bash
apex submit tracks/main/dist/solution.py -c <competition id>
```

It pays the competition's submission fee in TAO from your coldkey, asking for the coldkey
password, and uploads the file signed with the hotkey. Rewards are winner-takes-all, so a
submission that doesn't top the leaderboard loses its fee. The full list of steps is in
`AGENTS.md` and `tracks/main/.taoloop/track.json`.

## Layout

- `tracks/main/`: the miner: `solution.py` (candidate), `miner.py` (check/evaluate/run),
  `tests/`, `requirements.txt` and `vendor/` (upstream evaluator, MIT, see `vendor/UPSTREAM.md`).
- `.taoloop/`: line manifest and agent role instructions.
- `AGENTS.md`: the full guide for coding agents.

Licence: MIT (`LICENSE`). Vendored upstream code keeps its own MIT licence in
`tracks/main/vendor/LICENSE`.
