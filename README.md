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

## Submitting (you, not an agent)

Submitting costs TAO and signs with your hotkey:

1. Install the Apex CLI (`./install_cli.sh` in a clone of https://github.com/macrocosm-os/apex).
2. Register a hotkey on netuid 1.
3. Run `apex link`.
4. Run `apex competitions` to find the energy_arbitrage id and its fee.
5. Run `apex submit tracks/main/dist/solution.py -c <id>`.

The full list is in `AGENTS.md` and `tracks/main/.taoloop/track.json`. Rewards are
winner-takes-all, so a submission that doesn't top the leaderboard loses its fee.

## Layout

- `tracks/main/`: the miner: `solution.py` (candidate), `miner.py` (check/evaluate/run),
  `tests/`, `requirements.txt` and `vendor/` (upstream evaluator, MIT, see `vendor/UPSTREAM.md`).
- `.taoloop/`: line manifest and agent role instructions.
- `AGENTS.md`: the full guide for coding agents.

Licence: MIT (`LICENSE`). Vendored upstream code keeps its own MIT licence in
`tracks/main/vendor/LICENSE`.
