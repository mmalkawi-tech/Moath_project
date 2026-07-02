# Shared across dev/test/production: one registry avoids paying for three,
# and lets the same built image be promoted across environments by tag.
resource "azurerm_resource_group" "shared" {
  name     = "${var.project_name}-shared-rg"
  location = var.location
}

resource "azurerm_container_registry" "acr" {
  name                = "${var.project_name}acr"
  resource_group_name = azurerm_resource_group.shared.name
  location            = azurerm_resource_group.shared.location
  sku                 = "Basic"
  admin_enabled       = true
}
