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
  description = "Resource group the monitoring resources are deployed into"
  type        = string
}

variable "retention_in_days" {
  description = "Log Analytics retention (30 is the minimum / cheapest for PerGB2018)"
  type        = number
  default     = 30
}
