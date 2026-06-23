# Contributing to FH6 AutoBot

Thanks for your interest in improving FH6 AutoBot! Bug reports, feature ideas, and pull
requests are all welcome.

## Development setup

```bash
git clone https://github.com/hypoxic127/FH6-AFK.git
cd FH6-AFK
python setup.py          # creates a venv and installs dependencies
```

Runtime requires **Windows + Tesseract OCR + ViGEmBus**, with the game running in English,
windowed/borderless. Most perception/input code only runs on Windows with the game open.

## Before opening a pull request

```bash
python -m ruff check .          # lint
python -m ruff format --check . # formatting (line length 120, double quotes)
python -m pytest                # tests (hardware tests are auto-excluded)
```

- Hardware tests (vgamepad / MSS / the game window) are skipped by default via `pytest.ini`
  (`-m "not hardware"`). Run them with `python -m pytest -m hardware` only on Windows with the
  game open.
- A git hook (`core.hooksPath=.githooks`) runs `ruff format` on staged `.py` files at commit
  time and re-stages them, so commits stay formatted.

## Pull request workflow

1. Fork the repo and create a branch: `git checkout -b feat/your-feature`
2. Make your change; keep it focused and match the surrounding code style.
3. Run lint, format, and tests (above).
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat` / `fix` / `docs` / `refactor` / `chore` / `test`).
5. Push and open a PR. **All PRs must pass CI (Lint + Test).**

## Architecture quick reference

Four layers with a strict one-way dependency direction (`web → macro / farm → engine`, never
the reverse):

- **`engine/`** — perception + infrastructure (OCR, state detection, capture, gamepad, i18n,
  updater)
- **`macro/`** — the master state machine and per-stage menu macros
- **`farm/`** — the EventLab auto-driving sub-state-machine
- **`web/`** — Flask + SocketIO server and the dashboard

To surface something new in the UI, emit an event on the bus (`engine/event_bus.py`) and bridge
it in `web/server.py` — never import `web` from `engine`/`macro`.

## Reporting bugs

Please use the issue templates and include your OS version, game resolution, Tesseract version,
clear reproduction steps, and relevant logs.
