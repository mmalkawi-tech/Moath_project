# Moath Clinic

A pharmacy & prescription management API, deployed to Azure across **dev / test / production**
environments with a fully automated CI/CD pipeline, container image scanning, and Azure Monitor
observability. Every resource is sized on the cheapest viable Azure tier.

## Stack

- **App**: Python/Flask + SQLAlchemy, containerized with Docker (`app/`)
- **Infrastructure**: Terraform on Azure (`terraform/`) — a shared ACR plus one isolated
  environment (resource group, AKS, Postgres Flexible Server, Log Analytics + App Insights) per
  dev/test/production, built from reusable modules; remote state in Azure Blob Storage, one
  state file per environment
- **Runtime**: Kubernetes manifests for AKS (`k8s/`) — Kustomize base + per-environment overlays
- **CI/CD**: Azure DevOps Pipeline (`azure-pipelines.yml` + `pipelines/templates/`) for
  build/scan/deploy, plus a lightweight GitHub Actions workflow
  (`.github/workflows/pr-checks.yml`) for fast, credential-free PR feedback
- **Testing**: pytest unit tests for the API (`app/tests/`), gating the build in both pipelines
- **Security**: Trivy container image scan gates every deploy; tfsec scans the Terraform on every
  PR
- **Monitoring**: Azure Monitor Container Insights (cluster/pod metrics & logs) + Application
  Insights (in-app request/exception telemetry via `azure-monitor-opentelemetry`) — one workspace
  per environment

See [docs/architecture.md](docs/architecture.md) for the full diagram and component breakdown.

## Environments

| Environment | Branch | AKS nodes | VM size | Postgres SKU | Public access |
|---|---|---|---|---|---|
| dev | `develop` | 1 | `Standard_B2s` (burstable) | `B_Standard_B1ms` (burstable) | `kubectl port-forward` only |
| test | `test` | 1 | `Standard_B2s` (burstable) | `B_Standard_B1ms` (burstable) | `kubectl port-forward` only |
| production | `main` | 2 | `Standard_B2s` (burstable) | `B_Standard_B1ms` (burstable) | LoadBalancer (public IP) |

Cost choices, applied everywhere:
- **AKS**: `sku_tier = "Free"` control plane (no uptime-SLA charge), burstable `B2s` nodes, 1 node
  in dev/test (2 in production for basic availability — not 3, to stay cheap)
- **ACR**: a single **Basic**-tier registry shared by all three environments (build once, same
  image promoted by tag — one registry instead of three)
- **Postgres**: burstable `B_Standard_B1ms`, smallest allowed storage (32GB), one server per
  environment with its own database/credentials (kept separate for isolation — this is the one
  place environments are *not* shared)
- **Log Analytics**: 30-day retention (the minimum for `PerGB2018`, cheapest tier)
- **Networking**: dev/test stay `ClusterIP` (no public IP / LoadBalancer cost); only production
  gets a `LoadBalancer` Service

## Pipelines

**GitHub Actions** (`.github/workflows/pr-checks.yml`) — runs on every PR into `main`/`test`/
`develop`, no Azure credentials needed:
- `python-tests` — installs `app/requirements-dev.txt`, runs `pytest`
- `terraform-fmt` — `terraform fmt -check -recursive` across all of `terraform/`
- `terraform-validate` — `init -backend=false` + `validate`, matrixed over `acr` and each
  environment root
- `tfsec` — IaC security scan, matrixed the same way (scanning the whole `terraform/` tree in
  one shot doesn't work — tfsec treats each directory as its own root and silently stops after
  the first one; scanning per-root correctly resolves each environment's `module` blocks)

**Azure DevOps** (`azure-pipelines.yml`) — the actual build/scan/deploy pipeline, triggered on
every push/PR to `main`, `test`, or `develop`:

1. **Unit Tests** — same pytest suite, published as JUnit results; gates the build.
2. **Terraform - Shared ACR** — `init`/`validate`/`plan` always; `apply` on any of the three
   deploy branches (idempotent — whichever runs first creates it).
3. **Build & Push** — `az acr build` tags the image `$(Build.BuildId)` in the shared registry.
4. **Security Scan** — Trivy scans that image for HIGH/CRITICAL CVEs; a failure blocks every
   environment's deploy.
5. **Terraform + Deploy per environment** (`pipelines/templates/deploy-environment.yml`, invoked
   once per environment) — gated by branch:
   - `develop` → **dev**: Terraform apply, then deploy via `kubectl apply -k k8s/overlays/dev`
   - `test` → **test**: same, `k8s/overlays/test`
   - `main` → **production**: same, `k8s/overlays/production` — gated behind the
     `moathclinic-production` Azure DevOps environment's approval check

Each environment stage creates its Kubernetes namespace, the `moathclinic-db-secret` and
`moathclinic-appinsights-secret` from that environment's own Terraform outputs, then applies the
matching Kustomize overlay and waits for rollout.

## Local development

```bash
cd app
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
python app.py   # serves on :5000 against sqlite:///local_dev.db by default
```

Try it out:

```bash
curl -X POST localhost:5000/patients -H "Content-Type: application/json" \
  -d '{"full_name":"Jane Doe","date_of_birth":"1990-01-01"}'
curl -X POST localhost:5000/medications -H "Content-Type: application/json" \
  -d '{"name":"Amoxicillin 500mg","stock_quantity":100,"unit_price":4.5,"expiry_date":"2027-01-01"}'
curl -X POST localhost:5000/prescriptions -H "Content-Type: application/json" \
  -d '{"patient_id":1,"medication_id":1,"dosage":"1 tablet 3x/day","quantity":21,"prescribed_by":"Dr. Smith"}'
curl -X POST localhost:5000/prescriptions/1/dispense
```

### Running tests

```bash
cd app
pip install -r requirements-dev.txt
pytest
```

Tests run against a temporary SQLite file (set up in `conftest.py` before `app` is imported) so
they don't need Postgres or any Azure resource.

## Infrastructure

### Layout

```
terraform/
├── modules/            # reusable building blocks — no state of their own
│   ├── aks/
│   ├── database/
│   └── monitoring/
├── acr/                 # shared registry — own state, applied once
└── environments/
    ├── dev/              # own state, own resource group, calls the modules
    ├── test/
    └── production/
```

Each of `acr/` and `environments/{dev,test,production}/` is an independent root module with its
own remote-state key — a change (or a broken `plan`) in one environment can't corrupt another's
state.

### One-time setup

The remote state backend must exist before any `terraform init` (Terraform can't create its own
backend storage):

```bash
az group create --name moathclinic-tfstate-rg --location eastus
az storage account create --name moathclinictfstate123 --resource-group moathclinic-tfstate-rg \
  --sku Standard_LRS --encryption-services blob
az storage container create --name tfstate --account-name moathclinictfstate123
```

Apply the shared ACR first (environments read its state via `terraform_remote_state`):

```bash
cd terraform/acr
terraform init
terraform apply
```

Then each environment:

```bash
cd terraform/environments/dev   # or test / production
terraform init
terraform plan
terraform apply
```

State is stored remotely in `moathclinic-tfstate-rg` / `moathclinictfstate123`, one blob per
environment (`moathclinic-acr.terraform.tfstate`, `moathclinic-dev.terraform.tfstate`, etc.) —
never commit `*.tfstate` (already gitignored).

## Prerequisites for the pipeline

- Azure DevOps service connection `moath-sp-new` (Azure Resource Manager, scoped to the target
  subscription)
- GitHub service connection authorizing the Azure DevOps project to read this repo
- Three Azure DevOps environments: `moathclinic-dev`, `moathclinic-test`,
  `moathclinic-production` (auto-created on first deploy to each; add an approval check on
  `moathclinic-production` to require manual sign-off before prod deploys)
- `develop` and `test` branches created in the repo (in addition to `main`) — the pipeline
  deploys to dev/test only when those branches are pushed to
- Trivy needs no separate credentials — it authenticates against ACR via `az acr login` in the
  same pipeline identity as the build stage

## Branching & contribution workflow

`main` is treated as protected — it should only ever move forward via a reviewed pull request,
never a direct push (infrastructure changes go through `terraform plan` on the PR before anyone
applies them). Feature branches merge into `develop`; `develop` promotes to `test`; `test`
promotes to `main` for production.

1. Branch off `develop`: `git checkout -b <type>/<short-description>` (`feat/`, `fix/`,
   `chore/`, `infra/` prefixes)
2. Commit, push the branch, open a PR into `develop` (auto-deploys to **dev** once merged)
3. Promote via PR: `develop` → `test` (deploys to **test**), `test` → `main` (deploys to
   **production**, behind the approval gate)

**`main` branch protection is enabled**: pull request required (0 required approvals, since
this is a solo-maintainer repo and GitHub won't count self-approval anyway), conversation
resolution required, enforced for admins too, no force-push or deletion. Configured via:

```bash
cat > protection.json <<'EOF'
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "restrictions": null,
  "required_conversation_resolution": true
}
EOF
gh api repos/mmalkawi-tech/Moath_project/branches/main/protection --method PUT --input protection.json
```

(`required_status_checks` is left unset rather than pinned to the current tfsec/terraform-validate
matrix job names — those change whenever an environment is added or renamed, and a stale required
check name silently blocks all merges. Revisit once the check set stabilizes.)
