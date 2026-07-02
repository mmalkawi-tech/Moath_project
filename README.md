# Moath Clinic

A pharmacy & prescription management API, deployed to Azure with a fully automated CI/CD
pipeline, container image scanning, and Azure Monitor observability.

## Stack

- **App**: Python/Flask + SQLAlchemy, containerized with Docker (`app/`)
- **Infrastructure**: Terraform on Azure (`terraform/`) — resource group, Azure Container
  Registry, AKS cluster (with Container Insights), Postgres Flexible Server, Log Analytics
  Workspace + Application Insights, remote state in Azure Blob Storage
- **Runtime**: Kubernetes manifests for AKS (`k8s/`) — Deployment + LoadBalancer Service
- **CI/CD**: Azure DevOps Pipeline (`azure-pipelines.yml`), source hosted on GitHub
- **Security**: Trivy container image scan gates every deploy
- **Monitoring**: Azure Monitor Container Insights (cluster/pod metrics & logs) + Application
  Insights (in-app request/exception telemetry via `opencensus`)

See [docs/architecture.md](docs/architecture.md) for the full diagram and component breakdown.

## Pipeline

Triggered on every push/PR to `main`, four stages:

1. **Terraform** — `init` / `validate` / `plan` always; `apply` only when running on `main`.
   Publishes DB connection details, the ACR login server, and the App Insights connection
   string as pipeline outputs for later stages.
2. **Build & Push** — `az acr build` builds the Docker image directly in ACR and tags it with
   both `latest` and the build ID. Runs only on `main`.
3. **Security Scan** — installs Trivy and scans the freshly built image for HIGH/CRITICAL CVEs;
   fails the pipeline (blocking deploy) if any unfixed vulnerabilities are found.
4. **Deploy to AKS** — fetches AKS credentials, creates/updates the `moathclinic-db-secret` and
   `moathclinic-appinsights-secret` from the Terraform outputs, injects the freshly built image
   tag into `k8s/deployment.yaml`, applies the manifests, and waits for rollout.

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

## Infrastructure

Before the first `terraform init`, the remote state backend must exist (Terraform can't create
its own backend storage):

```bash
az group create --name moathclinic-tfstate-rg --location eastus
az storage account create --name moathclinictfstate123 --resource-group moathclinic-tfstate-rg \
  --sku Standard_LRS --encryption-services blob
az storage container create --name tfstate --account-name moathclinictfstate123
```

Then:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

State is stored remotely in the `moathclinic-tfstate-rg` / `moathclinictfstate123` storage
account — never commit `*.tfstate` (already gitignored).

## Prerequisites for the pipeline

- Azure DevOps service connection `moath-sp-new` (Azure Resource Manager, scoped to the target
  subscription)
- GitHub service connection authorizing the Azure DevOps project to read this repo
- Environment `moathclinic-production` (auto-created on first deploy; add an approval check on
  it to require manual sign-off before deploys)
- Trivy needs no separate credentials — it authenticates against ACR via `az acr login` in the
  same pipeline identity as the build stage
