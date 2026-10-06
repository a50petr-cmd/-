# job-agent monorepo (Petro)

Personal automation: job search, price comparison, e-grocery basket (in progress).

## E-grocery basket (P0)

Branch: `cursor/e-grocery-basket-p0`

```powershell
cd $HOME\job-agent
git checkout cursor/e-grocery-basket-p0
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:JOB_AGENT_STORE = "$HOME\job-agent-store"
python -m egrocery basket
```

Config YAMLs live in the agent store (`docs/e-grocery-location.yaml`, `docs/e-grocery-basket-starter.yaml`). See [docs/e-grocery-basket-mvp.md](./docs/e-grocery-basket-mvp.md).
