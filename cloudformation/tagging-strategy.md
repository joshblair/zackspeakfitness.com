# Tagging Strategy for Static Website Infrastructure

## Overview
This document defines the consistent tagging strategy for all AWS resources in the static website infrastructure to enable cost tracking, resource management, and operational excellence.

## Standard Tags

All resources MUST include these standard tags:

### Required Tags
- **Name**: Descriptive name of the resource
- **Environment**: Environment name (dev, staging, prod)
- **Project**: Project identifier (static-website)
- **Owner**: Resource owner (zackspeakfitness)
- **CostCenter**: Cost allocation identifier (website-operations)
- **Component**: Infrastructure component (storage, distribution, dns, certificate, cicd, monitoring)
- **ManagedBy**: How the resource is managed (CloudFormation)
- **CreatedDate**: Resource creation date (YYYY-MM-DD)

### Optional Tags
- **Purpose**: Specific purpose of the resource
- **Security**: Security classification or requirements
- **Backup**: Backup requirements (if applicable)
- **Monitoring**: Monitoring requirements
- **Compliance**: Compliance requirements

## Cost Allocation Tags

For cost tracking and billing analysis:

- **CostCenter**: website-operations
- **Project**: static-website
- **Environment**: dev/staging/prod
- **Component**: storage/distribution/dns/certificate/cicd/monitoring

## Tag Values by Component

### Storage Component
- Component: storage
- Purpose: Static Website Hosting / CloudFront Access Logs
- Security: OAC-Protected / Private

### Distribution Component  
- Component: distribution
- Purpose: Global Content Delivery
- Security: HTTPS-Only

### DNS Component
- Component: dns
- Purpose: Domain Name Resolution
- Monitoring: Health Checks Enabled

### Certificate Component
- Component: certificate
- Purpose: SSL/TLS Encryption
- Security: TLS 1.2+

### CI/CD Component
- Component: cicd
- Purpose: Automated Deployment
- Security: OIDC Authentication

### Monitoring Component
- Component: monitoring
- Purpose: Infrastructure Monitoring
- Monitoring: Alerts Enabled

## Implementation

Tags are implemented in CloudFormation templates using:
1. Resource-level Tags property
2. Stack-level Tags (inherited by all resources)
3. Consistent tag values across all templates