resource "azurerm_resource_group" "main" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location
}

# Reads the shared ACR's outputs (id, name, login server) from its own state
# file so this environment doesn't create - or pay for - its own registry.
data "terraform_remote_state" "acr" {
  backend = "azurerm"
  config = {
    resource_group_name  = "moathclinic-tfstate-rg"
    storage_account_name = "moathclinictfstate123"
    container_name       = "tfstate"
    key                  = "moathclinic-acr.terraform.tfstate"
  }
}

module "monitoring" {
  source = "../../modules/monitoring"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
}

module "aks" {
  source = "../../modules/aks"

  project_name               = var.project_name
  environment                = var.environment
  location                   = var.location
  resource_group_name        = azurerm_resource_group.main.name
  aks_node_count             = var.aks_node_count
  aks_vm_size                = var.aks_vm_size
  log_analytics_workspace_id = module.monitoring.log_analytics_workspace_id
  acr_id                     = data.terraform_remote_state.acr.outputs.acr_id
}

module "database" {
  source = "../../modules/database"

  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.main.name
}
