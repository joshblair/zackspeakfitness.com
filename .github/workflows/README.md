# GitHub Actions Workflows

This directory contains GitHub Actions workflows for the static website infrastructure project.

## Workflows

### 1. Deploy (`deploy.yml`)

**Purpose**: Automated deployment of website changes to AWS infrastructure.

**Triggers**:
- Push to `main` branch with changes to `website/**` or workflow files
- Manual workflow dispatch with environment selection

**Features**:
- HTML validation using `html-validate`
- Basic link checking
- AWS credential configuration via OIDC
- S3 file synchronization with cache control headers
- CloudFront cache invalidation
- Deployment verification
- Multi-environment support (dev/prod)

**Required Secrets**:
- `AWS_ROLE_ARN`: ARN of the GitHub Actions IAM role created by CloudFormation

**Environment Variables**:
- `AWS_REGION`: Set to `us-west-2`

### 2. Validate Pull Request (`validate-pr.yml`)

**Purpose**: Validation of changes in pull requests before merging.

**Triggers**:
- Pull requests to `main` branch with changes to website, infrastructure, or workflow files

**Features**:
- HTML file validation
- Basic CSS syntax checking
- Security issue detection (inline scripts, external links)
- CloudFormation template validation using `cfn-lint`
- Basic security scanning for secrets and credentials

## Setup Instructions

### 1. Configure AWS OIDC Authentication

The workflows use OpenID Connect (OIDC) for secure authentication with AWS. The IAM role and OIDC provider are created by the CloudFormation CI/CD stack.

1. Deploy the infrastructure including the CI/CD stack:
   ```bash
   cd cloudformation
   python deploy.py --environment prod
   ```

2. Get the GitHub Actions role ARN from CloudFormation outputs:
   ```bash
   aws cloudformation describe-stacks \
     --stack-name static-website-prod \
     --query 'Stacks[0].Outputs[?OutputKey==`GitHubActionsRoleArn`].OutputValue' \
     --output text
   ```

3. Add the role ARN as a repository secret:
   - Go to your GitHub repository
   - Navigate to Settings > Secrets and variables > Actions
   - Add a new repository secret named `AWS_ROLE_ARN`
   - Set the value to the role ARN from step 2

### 2. Environment Configuration

The workflows support multiple environments (dev/prod). Each environment should have:

1. A deployed CloudFormation stack named `static-website-{environment}`
2. The stack should output:
   - `BucketName`: S3 bucket name for website files
   - `DistributionId`: CloudFront distribution ID
   - `DomainName`: Website domain name

### 3. Website Structure

The workflows expect website files in the `website/` directory:

```
website/
├── index.html
├── about.html
├── services.html
├── contact.html
├── css/
│   └── main.css
├── js/
│   └── main.js
└── images/
    └── ...
```

If the `website/` directory doesn't exist, the deployment workflow will create a basic placeholder page.

## Workflow Behavior

### Deployment Process

1. **Validation**: HTML files are validated for syntax errors
2. **Authentication**: AWS credentials are configured using OIDC
3. **Stack Discovery**: CloudFormation outputs are retrieved for S3 bucket and CloudFront distribution
4. **File Sync**: Website files are synchronized to S3 with appropriate cache headers
5. **Cache Invalidation**: CloudFront cache is invalidated to serve updated content
6. **Verification**: Deployment success is verified by checking S3 file count

### Security Features

- **OIDC Authentication**: No long-lived AWS credentials stored in GitHub
- **Least Privilege**: IAM role has minimal required permissions
- **Content Validation**: HTML and basic security checks before deployment
- **Secret Scanning**: Basic checks for hardcoded credentials

### Error Handling

- **Validation Failures**: Deployment is blocked if HTML validation fails
- **AWS Errors**: Clear error messages for AWS API failures
- **Rollback**: CloudFormation provides automatic rollback on deployment failures
- **Notifications**: Clear success/failure notifications in workflow output

## Troubleshooting

### Common Issues

1. **Authentication Errors**:
   - Verify `AWS_ROLE_ARN` secret is correctly set
   - Ensure OIDC provider and IAM role are deployed
   - Check that repository name matches CloudFormation parameters

2. **Deployment Failures**:
   - Check CloudFormation stack status
   - Verify S3 bucket and CloudFront distribution exist
   - Ensure IAM role has required permissions

3. **Validation Errors**:
   - Fix HTML syntax errors reported by `html-validate`
   - Remove or fix broken links in HTML files
   - Address security warnings (inline scripts, etc.)

### Manual Deployment

To deploy manually using the same process:

```bash
# Configure AWS credentials
aws configure

# Get stack outputs
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name static-website-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' \
  --output text)

DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
  --stack-name static-website-prod \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
  --output text)

# Sync files
aws s3 sync website/ s3://$BUCKET_NAME --delete

# Invalidate cache
aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"
```

## Monitoring

The workflows provide detailed logging for:
- File validation results
- AWS API calls and responses
- Deployment progress and verification
- Error details and troubleshooting information

Monitor workflow runs in the GitHub Actions tab of your repository.