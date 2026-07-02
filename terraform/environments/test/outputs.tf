output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "aks_cluster_name" {
  value = module.aks.aks_cluster_name
}

output "acr_login_server" {
  value = data.terraform_remote_state.acr.outputs.acr_login_server
}

output "db_fqdn" {
  value = module.database.db_fqdn
}

output "db_name" {
  value = module.database.db_name
}

output "db_admin_login" {
  value = module.database.db_admin_login
}

output "db_password" {
  value     = module.database.db_password
  sensitive = true
}

output "app_insights_connection_string" {
  value     = module.monitoring.app_insights_connection_string
  sensitive = true
}
