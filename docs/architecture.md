# Moath Clinic — Architecture

## Overview

Pharmacy & prescription management API, containerized and deployed to Azure Kubernetes
Service, with images built and stored in Azure Container Registry, Postgres for persistence,
and Azure Monitor / Application Insights for observability.

## Diagram

```
                         Azure DevOps Pipeline
                                  │
        ┌─────────────────────────┼─────────────────────────┐
        │ 1. Terraform              2. az acr build            3. Trivy scan (gate)
        ▼                          ▼                           ▼
  Resource Group              ACR (moathclinicacr) ────────────┘
        │                          │  AcrPull role
        ├── AKS (moathclinic-aks) ◄┘
        │     └── Deployment: moathclinic-app (2 replicas)
        │           └── Service: LoadBalancer :80 → :5000
        ├── Postgres Flexible Server (moathclinic-psql)
        └── Log Analytics Workspace (moathclinic-logs)
                └── Container Insights (AKS oms_agent)
                └── Application Insights (moathclinic-appinsights)
                        └── in-app telemetry via opencensus
```

## Components

### Compute
- **AKS** (`moathclinic-aks`): system-assigned identity, `AcrPull` role on the ACR, Container
  Insights enabled via `oms_agent` pointing at the Log Analytics workspace.
- **ACR** (`moathclinicacr`): Basic SKU, images built directly in the registry via `az acr build`
  (no local Docker build step in CI).

### Data
- **Postgres Flexible Server** (`moathclinic-psql`): Postgres 16, `moathclinic` database,
  firewall rule allowing Azure services, admin password generated with `random_password` and
  passed to the app as a Kubernetes secret.

### Observability
- **Log Analytics Workspace** (`moathclinic-logs`): backs both Container Insights (AKS cluster
  and pod metrics/logs) and Application Insights.
- **Application Insights** (`moathclinic-appinsights`): workspace-based, connection string
  injected into the app via the `moathclinic-appinsights-secret` Kubernetes secret and
  `APPLICATIONINSIGHTS_CONNECTION_STRING` env var; the Flask app attaches `opencensus`'s
  `FlaskMiddleware` and `AzureLogHandler` only when that var is present.

### CI/CD (`azure-pipelines.yml`)

| Stage | Trigger | What it does |
|-------|---------|---------------|
| Terraform | Every push/PR | `init`/`validate`/`plan` always; `apply` only on `main`. Publishes DB, ACR, and App Insights outputs. |
| BuildAndPush | `main` only | `az acr build` tags the image with `latest` and the build ID. |
| SecurityScan | `main` only | Installs Trivy, scans the freshly built image for HIGH/CRITICAL CVEs, fails the pipeline (blocking deploy) on any unfixed match. |
| DeployToAKS | `main` only, after a clean scan | Fetches AKS credentials, creates/updates the DB and App Insights secrets, applies `k8s/` manifests, waits for rollout. |

## Domain model

- **Patient** — id, full_name, date_of_birth, phone
- **Medication** — id, name, stock_quantity, unit_price, expiry_date
- **Prescription** — id, patient_id, medication_id, dosage, quantity, prescribed_by,
  prescribed_at, dispensed

Dispensing a prescription (`POST /prescriptions/<id>/dispense`) atomically decrements
`Medication.stock_quantity` and marks the prescription as dispensed, rejecting the request with
a 400 if stock is insufficient.
