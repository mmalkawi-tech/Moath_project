output "acr_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "aks_cluster_name" {
  value = azurerm_kubernetes_cluster.aks.name
}

output "resource_group_name" {
  value = azurerm_resource_group.main.name
}

output "db_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "db_password" {
  value     = random_password.db_password.result
  sensitive = true
}

output "app_insights_connection_string" {
  value     = azurerm_application_insights.main.connection_string
  sensitive = true
}
