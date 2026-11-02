# buggy-site-meadowbrook: Meadowbrook Clinic

Meadowbrook Clinic is a demo GP patient portal (find a clinician, book, move and cancel appointments, repeat
prescriptions, test results, messages, children on your account, your details, and a reception desk) with **40
functional bugs planted on purpose**, to measure how many the AI QA Scanner finds. It is the seventh benchmark site,
after [buggy-site](https://github.com/Chaman-Raghav-Inno/buggy-site) (Lumen Goods),
[buggy-site-taskline](https://github.com/Chaman-Raghav-Inno/buggy-site-taskline) (Taskline),
[buggy-site-driftwood](https://github.com/Chaman-Raghav-Inno/buggy-site-driftwood) (Driftwood Stays),
[buggy-site-fernhill](https://github.com/Chaman-Raghav-Inno/buggy-site-fernhill) (Fernhill Academy),
[buggy-site-kestrel](https://github.com/Chaman-Raghav-Inno/buggy-site-kestrel) (Kestrel Works) and
[buggy-site-copperleaf](https://github.com/Chaman-Raghav-Inno/buggy-site-copperleaf) (Copperleaf Bank). Its bugs break
clinic rules: opening hours, lunch and closed days, appointment lengths, leave, double bookings, cancellation fees,
prescription limits and intervals, reference ranges, patient privacy, NHS number checks and the reception desk.

It is not a real clinic and gives no medical advice; everyone in it is fictional, and it says so on every page.

[BUGS.md](BUGS.md) is the answer key: for each bug, the steps to reproduce, what should happen, what happens, its
severity, how hard it is to notice and where it is in the code. The site never serves that file, and nothing it
serves names or hints at a bug. The rules each bug breaks are published on the site (`/help`).

## Run it

```sh
python -m meadowbrook          # http://localhost:8086 (PORT changes the port)
```

Standard library only (Python 3.11+); no install step.

- Accounts (password `Meadowbrook@2026`, shown on the login page): `ava@meadowbrook.test` (patient, with her son
  Leo on her family page), `kai@meadowbrook.test` (receptionist: day list, check-in, blocking times).
- Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
  other's changes. Both accounts share that copy within one browser. A restart or redeploy resets everything.

## Deploy on Railway

New service → GitHub repo → this repository, then **Generate domain** under Networking. `railway.json` sets the
start command and health check (`/healthz`); no variables or volume are needed. Avoid redeploying while a scan runs.

## Development

```sh
pip install ruff pytest
ruff check . && ruff format --check .
pytest -q
```

`tests/test_meadowbrook.py` keeps the server-side bugs in place and checks that nothing served gives a bug away.
Server-side code marks each bug with a `BUG-nn` comment; the served files must not.
