variable "project_name" {
  description = "Name prefix used for all resources"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, test, production)"
  type        = string
}

variable "location" {
  description = "Azure region"
  type        = string
}

variable "resource_group_name" {
  description = "Resource group the cluster is deployed into"
  type        = string
}

variable "aks_node_count" {
  description = "Number of nodes in the AKS default node pool"
  type        = number
}

variable "aks_vm_size" {
  description = "VM size for AKS nodes (kept on the burstable B-series for cost)"
  type        = string
}

variable "log_analytics_workspace_id" {
  description = "Log Analytics workspace ID for Container Insights"
  type        = string
}

variable "acr_id" {
  description = "Resource ID of the shared ACR, for AcrPull role assignment"
  type        = string
}
