output "public_ip" {
  description = "Point the domain's A records here"
  value       = azurerm_public_ip.main.ip_address
}

output "ssh_command" {
  value = "ssh -p ${var.admin_ssh_port} ${var.admin_username}@${azurerm_public_ip.main.ip_address}"
}
