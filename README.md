# ZackSpeakFitness Website

A production-ready static website infrastructure for zackspeakfitness.com built with AWS services and Infrastructure as Code principles.

## Project Structure

```
├── cloudformation/          # Infrastructure as Code templates and scripts
│   ├── templates/          # Modular CloudFormation templates
│   ├── parameters/         # Environment-specific parameters
│   ├── master-template.yaml # Main orchestration template
│   ├── deploy.py          # Python deployment script
│   ├── Makefile           # Deployment automation
│   └── README.md          # Infrastructure documentation
├── website/               # Static website content (to be created)
├── .github/               # GitHub Actions workflows (to be created)
└── .kiro/                 # Kiro specification files
    └── specs/
        └── static-website-infrastructure/
            ├── requirements.md # Feature requirements
            ├── design.md      # Technical design
            └── tasks.md       # Implementation tasks
```

## Quick Start

### 1. Deploy Infrastructure

```bash
cd cloudformation
make install
make deploy TEMPLATE_BUCKET=your-cloudformation-templates-bucket
```

### 2. Configure GitHub Actions

After deployment, add these secrets to your GitHub repository:
- `AWS_ROLE_ARN`: From stack outputs
- `S3_BUCKET_NAME`: From stack outputs  
- `CLOUDFRONT_DISTRIBUTION_ID`: From stack outputs

### 3. Deploy Website Content

Push website files to trigger automated deployment via GitHub Actions.

## Architecture

The infrastructure uses AWS services following the Well-Architected Framework:

- **S3**: Secure static website storage with Origin Access Control
- **CloudFront**: Global CDN with custom domain and SSL
- **ACM**: SSL/TLS certificate with DNS validation
- **Route 53**: DNS management for custom domain
- **GitHub Actions**: Automated CI/CD deployment

## Features

- ✅ **HTTPS Only**: Automatic HTTP to HTTPS redirects
- ✅ **Global CDN**: CloudFront edge locations worldwide
- ✅ **Security Headers**: HSTS, X-Content-Type-Options, X-Frame-Options
- ✅ **Origin Access Control**: Prevents direct S3 access
- ✅ **Automated Deployment**: GitHub Actions CI/CD pipeline
- ✅ **Infrastructure as Code**: CloudFormation templates
- ✅ **Cost Optimized**: Efficient caching and compression
- ✅ **Monitoring Ready**: CloudWatch integration

## Documentation

- [Infrastructure Documentation](cloudformation/README.md)
- [Requirements Specification](.kiro/specs/static-website-infrastructure/requirements.md)
- [Technical Design](.kiro/specs/static-website-infrastructure/design.md)
- [Implementation Tasks](.kiro/specs/static-website-infrastructure/tasks.md)

## Development

This project follows a specification-driven development approach using Kiro. The complete feature specification includes:

1. **Requirements**: Formal requirements using EARS patterns
2. **Design**: Comprehensive technical design with correctness properties
3. **Tasks**: Actionable implementation plan with testing strategy

## License

This project is provided as-is for educational and production use.
