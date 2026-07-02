variable "project_name" {
  description = "Name prefix used for all resources"
  type        = string
  default     = "moathclinic"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

variable "aks_node_count" {
  description = "Number of nodes in the AKS default node pool (2 for basic availability, still the cheapest VM size)"
  type        = number
  default     = 2
}

variable "aks_vm_size" {
  description = "VM size for AKS nodes"
  type        = string
  default     = "Standard_B2s"
}
