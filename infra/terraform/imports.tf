# The VM was first created by hand with `az vm create`. These blocks adopt it into
# Terraform state on the first `terraform apply`, without recreating anything.
# Delete this file once the import has been applied.

locals {
  rg_id = "/subscriptions/${var.subscription_id}/resourceGroups/${var.resource_group}"
  net   = "${local.rg_id}/providers/Microsoft.Network"
}

import {
  to = azurerm_resource_group.main
  id = local.rg_id
}

import {
  to = azurerm_virtual_network.main
  id = "${local.net}/virtualNetworks/${var.vm_name}VNET"
}

import {
  to = azurerm_subnet.main
  id = "${local.net}/virtualNetworks/${var.vm_name}VNET/subnets/${var.vm_name}Subnet"
}

import {
  to = azurerm_public_ip.main
  id = "${local.net}/publicIPAddresses/${var.vm_name}PublicIP"
}

import {
  to = azurerm_network_security_group.main
  id = "${local.net}/networkSecurityGroups/${var.vm_name}NSG"
}

import {
  to = azurerm_network_interface.main
  id = "${local.net}/networkInterfaces/${var.vm_name}VMNic"
}

import {
  to = azurerm_linux_virtual_machine.main
  id = "${local.rg_id}/providers/Microsoft.Compute/virtualMachines/${var.vm_name}"
}

import {
  to = azurerm_network_interface_security_group_association.main
  id = "${local.net}/networkInterfaces/${var.vm_name}VMNic|${local.net}/networkSecurityGroups/${var.vm_name}NSG"
}
