# Terraform configuration for Azure resources
# Creates AKS cluster, PostgreSQL database, and Event Hubs

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
  
  backend "azurerm" {
    # Configure backend in terraform.tfvars or via environment variables
    # resource_group_name = "terraform-state-rg"
    # storage_account_name = "terraformstate"
    # container_name = "tfstate"
    # key = "recommendation-system.terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
  
  subscription_id = var.azure_subscription_id
  tenant_id       = var.azure_tenant_id
  client_id       = var.azure_client_id
  client_secret   = var.azure_client_secret
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    Environment = var.environment
    Project     = "recommendation-system"
  }
}

# AKS Cluster
resource "azurerm_kubernetes_cluster" "main" {
  name                = var.aks_cluster_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = var.aks_cluster_name
  kubernetes_version  = "1.28"

  default_node_pool {
    name       = "default"
    node_count = var.aks_node_count
    vm_size    = var.aks_node_size
  }

  identity {
    type = "SystemAssigned"
  }

  network_profile {
    network_plugin    = "kubenet"
    load_balancer_sku = "standard"
  }

  tags = {
    Environment = var.environment
  }
}

# Azure Database for PostgreSQL
resource "azurerm_postgresql_server" "main" {
  name                         = var.postgres_server_name
  location                     = azurerm_resource_group.main.location
  resource_group_name          = azurerm_resource_group.main.name
  sku_name                     = "GP_Gen5_2"
  version                      = "11"
  administrator_login          = var.postgres_admin_user
  administrator_login_password = var.postgres_admin_password
  ssl_enforcement_enabled      = true

  tags = {
    Environment = var.environment
  }
}

resource "azurerm_postgresql_database" "main" {
  name                = "recommendation_db"
  resource_group_name = azurerm_resource_group.main.name
  server_name         = azurerm_postgresql_server.main.name
  charset             = "UTF8"
  collation           = "English_United States.1252"
}

# Event Hubs Namespace (alternative to Redpanda/Kafka)
resource "azurerm_eventhub_namespace" "main" {
  name                = var.event_hubs_namespace
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "Standard"
  capacity            = 1

  tags = {
    Environment = var.environment
  }
}

resource "azurerm_eventhub" "events" {
  name                = "user-events"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 2
  message_retention   = 1
}

resource "azurerm_eventhub" "features" {
  name                = "user-features"
  namespace_name      = azurerm_eventhub_namespace.main.name
  resource_group_name = azurerm_resource_group.main.name
  partition_count     = 2
  message_retention   = 1
}

# Outputs
output "aks_cluster_name" {
  value = azurerm_kubernetes_cluster.main.name
}

output "aks_cluster_fqdn" {
  value = azurerm_kubernetes_cluster.main.fqdn
}

output "postgres_server_fqdn" {
  value = azurerm_postgresql_server.main.fqdn
}

output "event_hubs_namespace" {
  value = azurerm_eventhub_namespace.main.name
}

