# sku_tier = Free avoids the Standard tier's uptime-SLA charge - fine for
# non-critical/portfolio workloads across all three environments.
#
# Restricting the API server to specific IPs would lock out the Azure DevOps
# Microsoft-hosted agents that run this pipeline (their egress IPs are drawn
# from a large, changing Microsoft range, not a fixed address). Doing this
# properly needs either self-hosted agents with a static IP or a private
# cluster - both add real cost/complexity beyond this project's
# cheapest-tier scope. Accepted risk, revisit if self-hosted agents are ever
# introduced.
#tfsec:ignore:azure-container-limit-authorized-ips
resource "azurerm_kubernetes_cluster" "aks" {
  name                              = "${var.project_name}-${var.environment}-aks"
  location                          = var.location
  resource_group_name               = var.resource_group_name
  oidc_issuer_enabled               = true
  dns_prefix                        = "${var.project_name}${var.environment}aks"
  sku_tier                          = "Free"
  role_based_access_control_enabled = true

  default_node_pool {
    name       = "default"
    node_count = var.aks_node_count
    vm_size    = var.aks_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  # calico works with the default kubenet plugin at no extra cost (Azure's
  # own network policy add-on requires the Azure CNI plugin, which consumes
  # a VNet IP per pod - kubenet+calico avoids that).
  network_profile {
    network_plugin = "kubenet"
    network_policy = "calico"
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
