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

# NOTE: cannot grant the pipeline's service principal rights to manage
# role assignments here (tried "User Access Administrator" scoped to just
# this ACR) - this subscription has an ABAC condition on every Owner
# role assignment that blocks granting privileged/access-management roles
# to anyone, including from an Owner account. This is a deliberate
# anti-privilege-escalation guardrail on the shared training subscription,
# not a bug to route around. See README's "Known limitation" section for
# the operational consequence and workaround.
