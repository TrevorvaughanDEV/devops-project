variable "subscription_id" {
  description = "Azure for Students subscription ID (az account show --query id -o tsv)"
  type        = string
}

variable "location" {
  description = "Azure for Students only allows a few regions; Spain Central has the B-series sizes"
  type        = string
  default     = "spaincentral"
}

variable "resource_group" {
  type    = string
  default = "devops-es"
}

variable "vm_name" {
  type    = string
  default = "devops-vm"
}

variable "vm_size" {
  description = "Smallest x64 size offered to the subscription in this region"
  type        = string
  default     = "Standard_B2ats_v2"
}

variable "admin_username" {
  type    = string
  default = "azureuser"
}

variable "admin_ssh_public_key" {
  description = "Public half of the key GitHub Actions and you use to log in"
  type        = string
}

variable "admin_ssh_port" {
  description = "Port for real SSH; 22 belongs to the honeypot"
  type        = number
  default     = 22022
}

variable "honeypot_ports" {
  description = "Public ports the honeypot answers on"
  type        = list(number)
  default     = [22, 2222]
}

variable "admin_source_cidrs" {
  description = "Who may reach real SSH. GitHub Actions runners need it too, so '*' with key-only login is the practical default"
  type        = list(string)
  default     = ["*"]
}
