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
  description = "Resource group the database is deployed into"
  type        = string
}

variable "sku_name" {
  description = "Postgres Flexible Server SKU (burstable B-series is the cheapest tier)"
  type        = string
  default     = "B_Standard_B1ms"
}

variable "storage_mb" {
  description = "Storage size in MB (32768 = 32GB is the smallest allowed)"
  type        = number
  default     = 32768
}
