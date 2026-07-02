variable "project_name" {
  description = "Name prefix used for all resources"
  type        = string
  default     = "moathclinic"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}
