# Terraform Configuration for Azure

This directory contains Terraform configuration to provision Azure resources for the recommendation system.

## Prerequisites

1. Azure CLI installed and logged in
2. Terraform >= 1.0 installed
3. Service principal with appropriate permissions

## Setup

### 1. Create Service Principal

```bash
az ad sp create-for-rbac --name "recommendation-system-sp" \
  --role contributor \
  --scopes /subscriptions/<subscription-id>
```

### 2. Configure Variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Plan Deployment

```bash
terraform plan
```

### 5. Apply Configuration

```bash
terraform apply
```

## Resources Created

- Resource Group
- AKS Cluster
- Azure Database for PostgreSQL
- Event Hubs Namespace and Topics

## Outputs

After applying, Terraform will output:
- AKS cluster name and FQDN
- PostgreSQL server FQDN
- Event Hubs namespace

## Cleanup

```bash
terraform destroy
```

## Notes

- Store `terraform.tfvars` securely (do not commit to git)
- Configure Terraform backend for state management
- Review and adjust resource sizes based on your needs

