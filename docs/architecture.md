# Moath Clinic — Architecture

## Overview

Pharmacy & prescription management API, deployed across three isolated Azure environments
(dev/test/production), each built from the same Terraform modules but sized on the cheapest
viable tier. A single shared Azure Container Registry serves all three — the app image is built
once per pipeline run and deployed into whichever environment its branch maps to.

## Diagram

```
                              Azure DevOps Pipeline
                                       │
        ┌───────────────┬─────────────┼──────────────┬────────────────┐
        │ 1. TF: ACR      2. az acr build   3. Trivy scan (gate)         │
        ▼               ▼                  ▼                            │
  moathclinic-shared-rg                                                  │
    └── ACR (moathclinicacr, Basic) ◄──── AcrPull role ─────┐            │
                                                              │            │
        ┌─────────────────────────────────────────────────────┴──────────┴───┐
        │  4. Per-environment Terraform + Deploy (branch-gated)                │
        ▼                          ▼                              ▼
  moathclinic-dev-rg        moathclinic-test-rg           moathclinic-production-rg
   (branch: develop)          (branch: test)                  (branch: main)
   ├── AKS (1 node,           ├── AKS (1 node,                ├── AKS (2 nodes,
   │   B2s, Free tier)        │   B2s, Free tier)              │   B2s, Free tier)
   │   ns: dev                │   ns: test                     │   ns: production
   │   Service: ClusterIP     │   Service: ClusterIP           │   Service: LoadBalancer
   ├── Postgres (B1ms)        ├── Postgres (B1ms)              ├── Postgres (B1ms)
   └── Log Analytics +        └── Log Analytics +               └── Log Analytics +
       App Insights               App Insights                     App Insights
```

## Components

### Terraform layout

```
terraform/
├── modules/              # no state — pure building blocks
│   ├── aks/                AKS cluster + AcrPull role assignment
│   ├── database/            Postgres Flexible Server + firewall + db
│   └── monitoring/           Log Analytics workspace + Application Insights
├── acr/                   # shared, own state (moathclinic-acr.terraform.tfstate)
└── environments/
    ├── dev/                 own state (moathclinic-dev.terraform.tfstate)
    ├── test/                own state (moathclinic-test.terraform.tfstate)
    └── production/          own state (moathclinic-production.terraform.tfstate)
```

Each environment reads the ACR's outputs via `terraform_remote_state` rather than creating its
own registry — a deliberate exception to "each environment is fully isolated," made purely for
cost (one Basic-tier ACR instead of three).

### Compute
- **AKS** per environment: `sku_tier = "Free"` (no control-plane SLA charge), burstable
  `Standard_B2s` nodes — 1 node in dev/test, 2 in production. System-assigned identity with
  `AcrPull` scoped to the shared ACR. Container Insights enabled via `oms_agent`. Kubernetes
  RBAC and a `calico` network policy (works with the default `kubenet` plugin at no extra
  cost) are both enabled. The API server is *not* IP-restricted — that would lock out the
  Azure DevOps Microsoft-hosted agents that run the pipeline; see the `tfsec:ignore` comment in
  `modules/aks/main.tf` for the accepted-risk rationale.
- **ACR** (shared, `moathclinicacr`): Basic SKU, images built directly in the registry via
  `az acr build` — one image per pipeline run, deployed into whichever environment the
  triggering branch maps to.

### Data
- **Postgres Flexible Server**, one per environment (`moathclinic-dev-psql`,
  `moathclinic-test-psql`, `moathclinic-production-psql`): Postgres 16, burstable
  `B_Standard_B1ms`, 32GB storage (smallest allowed), firewall rule allowing Azure services,
  admin password generated with `random_password` and injected as a namespaced Kubernetes
  secret. Kept separate per environment (unlike the ACR) so schema changes or load in one
  environment can't affect another.

### Kubernetes (`k8s/`)
- `base/`: Deployment (env vars for DB + App Insights via secretKeyRef, resource
  requests/limits, liveness/readiness probes on `/health`) + a `ClusterIP` Service.
- `overlays/{dev,test,production}/`: Kustomize overlays setting the namespace, image tag, and
  replica count; `overlays/production` patches the Service to `LoadBalancer` (the only
  environment with a public IP — dev/test are reached via `kubectl port-forward` to avoid
  paying for a LoadBalancer per non-prod environment).

### Observability
- One **Log Analytics Workspace** + **Application Insights** pair per environment (kept
  separate so telemetry doesn't mix across environments), 30-day retention (minimum for
  `PerGB2018`, cheapest tier).
- Connection string injected into the app via a namespaced `moathclinic-appinsights-secret` and
  `APPLICATIONINSIGHTS_CONNECTION_STRING`; the Flask app calls
  `azure-monitor-opentelemetry`'s `configure_azure_monitor()` only when that var is present,
  auto-instrumenting Flask, logging, and outbound requests.

### CI/CD

GitHub Actions (`.github/workflows/pr-checks.yml`) runs credential-free checks on every PR —
pytest, `terraform fmt`/`validate` (matrixed per root), and a matrixed tfsec scan (scanning the
whole `terraform/` tree in one pass doesn't work; tfsec stops after the first root it finds).

The Azure DevOps pipeline (`azure-pipelines.yml`) does the real build/scan/deploy:

| Stage | Trigger | What it does |
|-------|---------|---------------|
| Unit Tests | Every push/PR | pytest, published as JUnit results; gates the build. |
| Terraform - Shared ACR | Every push/PR on `main`/`test`/`develop` | `init`/`validate`/`plan` always; `apply` on any deploy branch (idempotent). |
| Build & Push | Any deploy branch | `az acr build` tags the image with the build ID. |
| Security Scan | After build | Trivy scans for HIGH/CRITICAL CVEs; failure blocks every environment's deploy. |
| Terraform + Deploy (dev) | `develop` only | Applies `terraform/environments/dev`, deploys `k8s/overlays/dev`. |
| Terraform + Deploy (test) | `test` only | Applies `terraform/environments/test`, deploys `k8s/overlays/test`. |
| Terraform + Deploy (production) | `main` only | Applies `terraform/environments/production`, deploys `k8s/overlays/production`, gated behind the `moathclinic-production` Azure DevOps environment's approval check. |

## Domain model

- **Patient** — id, full_name, date_of_birth, phone
- **Medication** — id, name, stock_quantity, unit_price, expiry_date
- **Prescription** — id, patient_id, medication_id, dosage, quantity, prescribed_by,
  prescribed_at, dispensed

Dispensing a prescription (`POST /api/prescriptions/<id>/dispense` for the JSON API, or the
"Dispense" button on `/prescriptions` for the GUI — both share the same `_dispense()` logic in
`app.py`) atomically decrements `Medication.stock_quantity` and marks the prescription as
dispensed, rejecting the request with a 400 if stock is insufficient.

## Web UI

Server-rendered with Flask + Jinja2 (`app/templates/`), styled with Bootstrap 5 via CDN (no
frontend build step — kept out of the Docker image and CI entirely):

- `/` — dashboard: patient/medication/prescription counts, low-stock medications, recent
  prescriptions
- `/patients`, `/medications`, `/prescriptions` — table views with a modal "add" form each;
  prescriptions additionally get a one-click "Dispense" button per pending row

The GUI and the `/api/*` JSON endpoints share the same SQLAlchemy models and, for dispensing,
the same `_dispense()` helper — the GUI redirects with a flash message on success/error, the API
returns JSON with the matching status code.
