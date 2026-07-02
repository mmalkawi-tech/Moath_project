output "db_fqdn" {
  value = azurerm_postgresql_flexible_server.main.fqdn
}

output "db_name" {
  value = azurerm_postgresql_flexible_server_database.app_db.name
}

output "db_admin_login" {
  value = azurerm_postgresql_flexible_server.main.administrator_login
}

output "db_password" {
  value     = random_password.db_password.result
  sensitive = true
}
