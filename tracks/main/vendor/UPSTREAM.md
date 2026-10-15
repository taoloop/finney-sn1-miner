# Vendored upstream code

`competition/` is copied from https://github.com/macrocosm-os/apex at commit
`da4a308ea7e097a1e357937e5a322a54bba9cc41`, path `shared/competition/src/competition/`
(only `__init__.py` and `energy_arbitrage/__init__.py` + `energy_arbitrage/python/`).
Licence: MIT, see `LICENSE` in this folder (copied verbatim from upstream).
`../requirements.txt` is upstream `energy_arbitrage/dockerfiles/requirements.txt`.

Local modification (the only one):

- `energy_arbitrage/python/utils.py`: `numpy` import made optional, with pure-Python
  Cholesky / SPD-inverse fallbacks used only when numpy is not installed. With the
  pinned `requirements.txt` installed the upstream numpy path runs unchanged.

Do not edit anything else here; this is the scorer. Re-sync from upstream instead.
