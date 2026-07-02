# sku_tier = Free avoids the Standard tier's uptime-SLA charge - fine for
# non-critical/portfolio workloads across all three environments.
resource "azurerm_kubernetes_cluster" "aks" {
  name                = "${var.project_name}-${var.environment}-aks"
  location            = var.location
  resource_group_name = var.resource_group_name
  oidc_issuer_enabled = true
  dns_prefix          = "${var.project_name}${var.environment}aks"
  sku_tier            = "Free"

  default_node_pool {
    name       = "default"
    node_count = var.aks_node_count
    vm_size    = var.aks_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  oms_agent {
    log_analytics_workspace_id = var.log_analytics_workspace_id
  }
}

# Allow this environment's AKS to pull images from the shared ACR
resource "azurerm_role_assignment" "aks_acr_pull" {
  principal_id                     = azurerm_kubernetes_cluster.aks.kubelet_identity[0].object_id
  role_definition_name             = "AcrPull"
  scope                            = var.acr_id
  skip_service_principal_aad_check = true
}
