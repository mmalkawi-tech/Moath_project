terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }

  # Separate state file from every environment - the registry is a
  # long-lived, shared resource that environments read via
  # terraform_remote_state rather than each creating their own.
  backend "azurerm" {
    resource_group_name  = "moathclinic-tfstate-rg"
    storage_account_name = "moathclinictfstate123"
    container_name       = "tfstate"
    key                  = "moathclinic-acr.terraform.tfstate"
  }
}
