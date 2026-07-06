resource "random_password" "db_password" {
  length  = 20
  special = false
}

resource "azurerm_postgresql_flexible_server" "main" {
  # "psql2" not "psql": Azure left a sticky cross-region name reservation
  # behind after a failed create in the wrong region (a subscription-level
  # location restriction, not a config error) - renaming sidesteps it.
  name                          = "${var.project_name}-${var.environment}-psql2"
  resource_group_name           = var.resource_group_name
  location                      = var.db_location
  version                       = "16"
  administrator_login           = "${var.project_name}_admin"
  administrator_password        = random_password.db_password.result
  storage_mb                    = var.storage_mb
  sku_name                      = var.sku_name
  zone                          = "1"
  public_network_access_enabled = true
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAzureServices"
  server_id        = azurerm_postgresql_flexible_server.main.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_postgresql_flexible_server_database" "app_db" {
  name      = "${var.project_name}_${var.environment}"
  server_id = azurerm_postgresql_flexible_server.main.id
  collation = "en_US.utf8"
  charset   = "utf8"
}
