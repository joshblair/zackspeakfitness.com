"""
Test configuration and fixtures for infrastructure validation tests.
"""
import pytest
import boto3
import os
from typing import Dict, Any


@pytest.fixture(scope="session")
def aws_credentials():
    """Ensure AWS credentials are available for testing."""
    # Check for AWS credentials
    session = boto3.Session()
    try:
        # This will raise an exception if no credentials are found
        session.get_credentials().get_frozen_credentials()
        return session
    except Exception as e:
        pytest.skip(f"AWS credentials not available: {e}")


@pytest.fixture(scope="session")
def acm_client(aws_credentials):
    """Create ACM client for certificate testing."""
    # ACM certificates for CloudFront must be in us-east-1
    return boto3.client('acm', region_name='us-east-1')


@pytest.fixture(scope="session")
def cloudformation_client(aws_credentials):
    """Create CloudFormation client for stack testing."""
    return boto3.client('cloudformation', region_name='us-west-2')


@pytest.fixture(scope="session")
def route53_client(aws_credentials):
    """Create Route 53 client for DNS testing."""
    return boto3.client('route53')


@pytest.fixture(scope="session")
def s3_client(aws_credentials):
    """Create S3 client for storage testing."""
    return boto3.client('s3', region_name='us-west-2')


@pytest.fixture(scope="session")
def cloudfront_client(aws_credentials):
    """Create CloudFront client for distribution testing."""
    return boto3.client('cloudfront')


@pytest.fixture(scope="session")
def cloudwatch_client(aws_credentials):
    """Create CloudWatch client for monitoring testing."""
    return boto3.client('cloudwatch', region_name='us-west-2')


@pytest.fixture(scope="session")
def sns_client(aws_credentials):
    """Create SNS client for notification testing."""
    return boto3.client('sns', region_name='us-west-2')


@pytest.fixture(scope="session")
def logs_client(aws_credentials):
    """Create CloudWatch Logs client for log group testing."""
    return boto3.client('logs', region_name='us-west-2')


@pytest.fixture(scope="session")
def test_config():
    """Test configuration parameters."""
    return {
        'domain_name': os.getenv('TEST_DOMAIN_NAME', 'zackspeakfitness.com'),
        'environment': os.getenv('TEST_ENVIRONMENT', 'test'),
        'stack_name': os.getenv('TEST_STACK_NAME', 'zackspeakfitness-test'),
        'master_stack_name': os.getenv('TEST_MASTER_STACK_NAME', 'zackspeakfitness-infrastructure-test'),
        'certificate_stack_name': os.getenv('TEST_CERT_STACK_NAME', 'zackspeakfitness-certificate-test'),
        'storage_stack_name': os.getenv('TEST_STORAGE_STACK_NAME', 'zackspeakfitness-storage-test'),
        'distribution_stack_name': os.getenv('TEST_DISTRIBUTION_STACK_NAME', 'zackspeakfitness-distribution-test'),
        'dns_stack_name': os.getenv('TEST_DNS_STACK_NAME', 'zackspeakfitness-dns-test'),
        'monitoring_stack_name': os.getenv('TEST_MONITORING_STACK_NAME', 'zackspeakfitness-monitoring-test'),
        'region': os.getenv('AWS_DEFAULT_REGION', 'us-west-2'),
        'certificate_region': 'us-east-1'  # Required for CloudFront certificates
    }