# Static Website Infrastructure

This directory contains CloudFormation templates and deployment scripts for a production-ready static website infrastructure on AWS.

## Architecture Overview

The infrastructure consists of the following components:
- **S3 Bucket**: Secure storage for static website files with Origin Access Control (OAC)
- **CloudFront Distribution**: Global CDN with custom domain and SSL certificate
- **ACM Certificate**: SSL/TLS certificate for HTTPS encryption
- **Route 53**: DNS management for custom domain
- **GitHub Actions IAM**: Roles and policies for automated CI/CD deployment

## Directory Structure

```
cloudformation/
├── templates/           # Modular CloudFormation templates
│   ├── certificate.yaml # ACM certificate with DNS validation
│   ├── storage.yaml     # S3 bucket with OAC security
│   ├── distribution.yaml# CloudFront distribution
│   ├── dns.yaml         # Route 53 DNS configuration
│   └── cicd.yaml        # GitHub Actions IAM roles
├── parameters/          # Environment-specific parameters
│   ├── prod.json        # Production parameters
│   └── dev.json         # Development parameters
├── master-template.yaml # Main template orchestrating nested stacks
├── deploy.py           # Python deployment script
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Prerequisites

1. **AWS CLI configured** with appropriate permissions
2. **Python 3.7+** installed
3. **Domain name** registered and accessible for DNS configuration
4. **S3 bucket** for storing nested CloudFormation templates

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Parameters

Edit the parameter files in `parameters/` directory:

- `prod.json`: Production environment settings
- `dev.json`: Development environment settings

Key parameters to update:
- `DomainName`: Your domain name (e.g., "example.com")
- `GitHubOrganization`: Your GitHub username or organization
- `GitHubRepository`: Your repository name
- `ExistingHostedZoneId`: If using existing Route 53 hosted zone

### 3. Create S3 Bucket for Templates

```bash
aws s3 mb s3://your-cloudformation-templates-bucket --region us-west-2
```

### 4. Deploy Infrastructure

```bash
# Upload templates and deploy production stack
python deploy.py \
  --stack-name zackspeakfitness-prod \
  --environment prod \
  --template-bucket your-cloudformation-templates-bucket \
  --upload-templates
```

### 5. Configure GitHub Repository

After deployment, configure your GitHub repository with the following secrets:

- `AWS_ROLE_ARN`: The GitHub Actions role ARN from stack outputs
- `S3_BUCKET_NAME`: The S3 bucket name from stack outputs  
- `CLOUDFRONT_DISTRIBUTION_ID`: The CloudFront distribution ID from stack outputs

## Deployment Commands

### Deploy Stack
```bash
python deploy.py \
  --stack-name <stack-name> \
  --environment <dev|staging|prod> \
  --template-bucket <bucket-name> \
  [--upload-templates] \
  [--region <aws-region>]
```

### Update Stack
```bash
# Same command as deploy - script detects existing stack
python deploy.py \
  --stack-name <stack-name> \
  --environment <environment> \
  --template-bucket <bucket-name>
```

### Delete Stack
```bash
python deploy.py \
  --stack-name <stack-name> \
  --delete
```

### Upload Templates Only
```bash
python deploy.py \
  --stack-name <stack-name> \
  --environment <environment> \
  --template-bucket <bucket-name> \
  --upload-templates
```

## Template Details

### Master Template (`master-template.yaml`)
Orchestrates all nested stacks with proper dependency management:
1. DNS Stack (creates hosted zone if needed)
2. Certificate Stack (depends on DNS for validation)
3. Storage Stack (S3 bucket and OAC)
4. Distribution Stack (CloudFront, depends on certificate and storage)
5. CI/CD Stack (GitHub Actions IAM, depends on storage and distribution)

### Certificate Template (`templates/certificate.yaml`)
- Creates ACM certificate for primary domain and www subdomain
- Uses DNS validation via Route 53
- Must be deployed in us-east-1 for CloudFront compatibility

### Storage Template (`templates/storage.yaml`)
- Creates S3 bucket with security best practices
- Configures Origin Access Control (OAC) for CloudFront
- Blocks all public access except through CloudFront
- Enables versioning and encryption

### Distribution Template (`templates/distribution.yaml`)
- Creates CloudFront distribution with custom domain
- Configures SSL certificate and security headers
- Sets up caching behaviors and compression
- Redirects HTTP to HTTPS

### DNS Template (`templates/dns.yaml`)
- Creates or uses existing Route 53 hosted zone
- Configures A records for apex and www domains
- Points to CloudFront distribution

### CI/CD Template (`templates/cicd.yaml`)
- Creates GitHub OIDC identity provider
- Creates IAM role for GitHub Actions
- Configures least-privilege permissions for deployment

## Security Features

- **Origin Access Control (OAC)**: Prevents direct S3 access
- **HTTPS Only**: Automatic HTTP to HTTPS redirects
- **Security Headers**: HSTS, X-Content-Type-Options, X-Frame-Options
- **Least Privilege IAM**: Minimal permissions for GitHub Actions
- **Encryption**: S3 server-side encryption enabled
- **No Public Access**: S3 bucket blocks all public access

## Cost Optimization

- **CloudFront Caching**: Reduces origin requests
- **Compression**: Automatic content compression
- **Standard Storage**: Cost-effective S3 storage class
- **Conditional Deployment**: Only deploys when changes detected

## Monitoring and Logging

- **CloudFront Access Logs**: Optional logging to S3
- **CloudWatch Integration**: Metrics and monitoring
- **Resource Tagging**: Consistent tagging for cost tracking
- **Stack Events**: Detailed deployment logging

## Troubleshooting

### Common Issues

1. **Certificate Validation Timeout**
   - Ensure DNS is properly configured
   - Check Route 53 hosted zone settings
   - Verify domain ownership

2. **S3 Bucket Name Conflicts**
   - Bucket names are globally unique
   - Script adds account ID suffix to prevent conflicts

3. **GitHub Actions Permission Errors**
   - Verify OIDC provider configuration
   - Check IAM role trust policy
   - Ensure repository name matches exactly

4. **CloudFront Distribution Errors**
   - Certificate must be in us-east-1
   - Verify OAC configuration
   - Check origin domain name

### Getting Help

1. Check CloudFormation stack events in AWS Console
2. Review deployment script output for detailed errors
3. Use `--region` flag if deploying to non-default region
4. Verify AWS credentials and permissions

## Next Steps

After successful deployment:

1. **Configure GitHub Actions**: Set up repository secrets
2. **Upload Website Content**: Deploy initial website files
3. **Test HTTPS**: Verify certificate and redirects work
4. **Monitor Performance**: Set up CloudWatch dashboards
5. **Configure Backups**: Set up S3 versioning and lifecycle policies

## License

This infrastructure code is provided as-is for educational and production use.