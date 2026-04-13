#!/usr/bin/env python3
"""
Test environment deployment script for static website infrastructure.
This script deploys the infrastructure in a test environment and validates all components.
"""

import argparse
import json
import sys
import time
import os
import requests
import ssl
import socket
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from deploy import CloudFormationDeployer


class TestEnvironmentDeployer(CloudFormationDeployer):
    """Extended deployer with test environment specific functionality."""
    
    def __init__(self, region: str = 'us-west-2'):
        """Initialize the test deployer."""
        super().__init__(region)
        self.test_results = []
    
    def create_test_template_bucket(self) -> str:
        """Create a unique S3 bucket for test templates."""
        import uuid
        bucket_suffix = str(uuid.uuid4())[:8]
        bucket_name = f"cf-templates-test-{bucket_suffix}-{self.region}"
        
        success = self.create_template_bucket(bucket_name)
        if success:
            return bucket_name
        else:
            raise Exception(f"Failed to create test template bucket: {bucket_name}")
    
    def deploy_test_stack(self, stack_name: str, domain_name: str) -> bool:
        """Deploy the complete test stack."""
        try:
            # Create template bucket
            print("Creating template bucket for test deployment...")
            template_bucket = self.create_test_template_bucket()
            print(f"Created template bucket: {template_bucket}")
            
            # Upload templates
            print("Uploading nested templates...")
            success = self.upload_templates(template_bucket)
            if not success:
                return False
            
            # Prepare test parameters
            parameters = [
                {
                    'ParameterKey': 'DomainName',
                    'ParameterValue': domain_name
                },
                {
                    'ParameterKey': 'Environment',
                    'ParameterValue': 'test'
                },
                {
                    'ParameterKey': 'GitHubOrganization',
                    'ParameterValue': 'test-org'
                },
                {
                    'ParameterKey': 'GitHubRepository',
                    'ParameterValue': 'test-repo'
                },
                {
                    'ParameterKey': 'CreateHostedZone',
                    'ParameterValue': 'true'
                },
                {
                    'ParameterKey': 'ExistingHostedZoneId',
                    'ParameterValue': ''
                },
                {
                    'ParameterKey': 'TemplateS3Bucket',
                    'ParameterValue': template_bucket
                }
            ]
            
            # Deploy the stack
            print(f"Deploying test stack: {stack_name}")
            success = self.deploy_stack(
                stack_name=stack_name,
                template_file='master-template.yaml',
                parameters=parameters
            )
            
            if success:
                print("✓ Test stack deployed successfully!")
                return True
            else:
                print("✗ Test stack deployment failed!")
                return False
                
        except Exception as e:
            print(f"Error deploying test stack: {e}")
            return False
    
    def validate_infrastructure_resources(self, stack_name: str) -> bool:
        """Validate that all AWS resources were created correctly."""
        print("\nValidating AWS resources...")
        
        try:
            # Get stack outputs
            outputs = self.get_stack_outputs(stack_name)
            if not outputs:
                print("✗ No stack outputs found")
                return False
            
            required_outputs = [
                'WebsiteURL',
                'CloudFrontDistributionId',
                'S3BucketName',
                'CertificateArn',
                'HostedZoneId'
            ]
            
            missing_outputs = [output for output in required_outputs if output not in outputs]
            if missing_outputs:
                print(f"✗ Missing required outputs: {missing_outputs}")
                return False
            
            print("✓ All required stack outputs present")
            
            # Validate individual resources
            validation_results = []
            
            # Validate S3 bucket
            bucket_name = outputs.get('S3BucketName')
            if bucket_name:
                bucket_valid = self._validate_s3_bucket(bucket_name)
                validation_results.append(('S3 Bucket', bucket_valid))
            
            # Validate CloudFront distribution
            distribution_id = outputs.get('CloudFrontDistributionId')
            if distribution_id:
                distribution_valid = self._validate_cloudfront_distribution(distribution_id)
                validation_results.append(('CloudFront Distribution', distribution_valid))
            
            # Validate ACM certificate
            certificate_arn = outputs.get('CertificateArn')
            if certificate_arn:
                cert_valid = self._validate_acm_certificate(certificate_arn)
                validation_results.append(('ACM Certificate', cert_valid))
            
            # Validate Route 53 hosted zone
            hosted_zone_id = outputs.get('HostedZoneId')
            if hosted_zone_id:
                dns_valid = self._validate_route53_hosted_zone(hosted_zone_id)
                validation_results.append(('Route 53 Hosted Zone', dns_valid))
            
            # Print validation results
            all_valid = True
            for resource, is_valid in validation_results:
                status = "✓" if is_valid else "✗"
                print(f"{status} {resource}: {'Valid' if is_valid else 'Invalid'}")
                if not is_valid:
                    all_valid = False
            
            return all_valid
            
        except Exception as e:
            print(f"Error validating infrastructure resources: {e}")
            return False
    
    def _validate_s3_bucket(self, bucket_name: str) -> bool:
        """Validate S3 bucket configuration."""
        try:
            # Check bucket exists
            self.s3_client.head_bucket(Bucket=bucket_name)
            
            # Check bucket policy (should deny direct access)
            try:
                policy_response = self.s3_client.get_bucket_policy(Bucket=bucket_name)
                policy = json.loads(policy_response['Policy'])
                
                # Look for deny statements
                has_deny_policy = False
                for statement in policy.get('Statement', []):
                    if statement.get('Effect') == 'Deny':
                        has_deny_policy = True
                        break
                
                if not has_deny_policy:
                    print(f"  Warning: Bucket {bucket_name} may not have proper access restrictions")
                
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchBucketPolicy':
                    print(f"  Warning: Could not check bucket policy: {e}")
            
            # Check encryption
            try:
                encryption_response = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
                print(f"  ✓ Bucket encryption enabled")
            except ClientError as e:
                if e.response['Error']['Code'] == 'ServerSideEncryptionConfigurationNotFoundError':
                    print(f"  Warning: Bucket encryption not configured")
                else:
                    print(f"  Warning: Could not check encryption: {e}")
            
            return True
            
        except ClientError as e:
            print(f"  Error validating S3 bucket: {e}")
            return False
    
    def _validate_cloudfront_distribution(self, distribution_id: str) -> bool:
        """Validate CloudFront distribution configuration."""
        try:
            cloudfront_client = boto3.client('cloudfront')
            
            response = cloudfront_client.get_distribution(Id=distribution_id)
            distribution = response['Distribution']
            config = distribution['DistributionConfig']
            
            # Check status
            status = distribution['Status']
            if status != 'Deployed':
                print(f"  Warning: Distribution status is {status}, not Deployed")
            
            # Check viewer protocol policy
            default_cache_behavior = config['DefaultCacheBehavior']
            viewer_protocol_policy = default_cache_behavior['ViewerProtocolPolicy']
            
            if viewer_protocol_policy not in ['redirect-to-https', 'https-only']:
                print(f"  Warning: Viewer protocol policy is {viewer_protocol_policy}")
                return False
            
            # Check custom domain
            aliases = config.get('Aliases', {}).get('Items', [])
            if not aliases:
                print(f"  Warning: No custom domain aliases configured")
            
            print(f"  ✓ Distribution configured with {len(aliases)} custom domain(s)")
            return True
            
        except ClientError as e:
            print(f"  Error validating CloudFront distribution: {e}")
            return False
    
    def _validate_acm_certificate(self, certificate_arn: str) -> bool:
        """Validate ACM certificate configuration."""
        try:
            # ACM certificates for CloudFront must be in us-east-1
            acm_client = boto3.client('acm', region_name='us-east-1')
            
            response = acm_client.describe_certificate(CertificateArn=certificate_arn)
            certificate = response['Certificate']
            
            # Check status
            status = certificate['Status']
            if status != 'ISSUED':
                print(f"  Warning: Certificate status is {status}, not ISSUED")
                return False
            
            # Check validation method
            validation_method = certificate.get('ValidationMethod')
            if validation_method != 'DNS':
                print(f"  Warning: Certificate validation method is {validation_method}")
            
            # Check domain names
            domain_name = certificate['DomainName']
            subject_alternative_names = certificate.get('SubjectAlternativeNames', [])
            
            print(f"  ✓ Certificate covers {len(subject_alternative_names) + 1} domain(s)")
            return True
            
        except ClientError as e:
            print(f"  Error validating ACM certificate: {e}")
            return False
    
    def _validate_route53_hosted_zone(self, hosted_zone_id: str) -> bool:
        """Validate Route 53 hosted zone configuration."""
        try:
            route53_client = boto3.client('route53')
            
            # Get hosted zone details
            response = route53_client.get_hosted_zone(Id=hosted_zone_id)
            hosted_zone = response['HostedZone']
            
            # Check if it's private
            if hosted_zone.get('Config', {}).get('PrivateZone', False):
                print(f"  Warning: Hosted zone is private")
                return False
            
            # Get record sets
            records_response = route53_client.list_resource_record_sets(HostedZoneId=hosted_zone_id)
            record_sets = records_response['ResourceRecordSets']
            
            # Check for A records
            a_records = [r for r in record_sets if r['Type'] == 'A']
            if not a_records:
                print(f"  Warning: No A records found in hosted zone")
            
            print(f"  ✓ Hosted zone contains {len(record_sets)} DNS records")
            return True
            
        except ClientError as e:
            print(f"  Error validating Route 53 hosted zone: {e}")
            return False
    
    def test_https_connectivity(self, domain_name: str) -> bool:
        """Test HTTPS connectivity and certificate validation."""
        print(f"\nTesting HTTPS connectivity for {domain_name}...")
        
        try:
            # Test HTTPS connection
            url = f"https://{domain_name}"
            
            # Create SSL context for certificate validation
            context = ssl.create_default_context()
            
            # Test connection with timeout
            response = requests.get(url, timeout=30, verify=True)
            
            if response.status_code == 200:
                print(f"✓ HTTPS connection successful (status: {response.status_code})")
                
                # Check security headers
                headers_to_check = [
                    'strict-transport-security',
                    'x-content-type-options',
                    'x-frame-options'
                ]
                
                missing_headers = []
                for header in headers_to_check:
                    if header not in response.headers:
                        missing_headers.append(header)
                
                if missing_headers:
                    print(f"  Warning: Missing security headers: {missing_headers}")
                else:
                    print("✓ All expected security headers present")
                
                return True
            else:
                print(f"✗ HTTPS connection failed (status: {response.status_code})")
                return False
                
        except requests.exceptions.SSLError as e:
            print(f"✗ SSL certificate validation failed: {e}")
            return False
        except requests.exceptions.ConnectionError as e:
            print(f"✗ Connection failed: {e}")
            return False
        except requests.exceptions.Timeout as e:
            print(f"✗ Connection timeout: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error testing HTTPS: {e}")
            return False
    
    def run_infrastructure_tests(self, stack_name: str) -> bool:
        """Run the complete infrastructure test suite."""
        print("\nRunning infrastructure validation tests...")
        
        try:
            # Import and run pytest tests
            import subprocess
            
            # Run the property-based tests
            result = subprocess.run([
                'python', '-m', 'pytest', 
                '../tests/', 
                '-v',
                '--tb=short',
                f'--stack-name={stack_name}'
            ], capture_output=True, text=True, cwd='.')
            
            if result.returncode == 0:
                print("✓ All infrastructure tests passed!")
                return True
            else:
                print("✗ Some infrastructure tests failed!")
                print("Test output:")
                print(result.stdout)
                if result.stderr:
                    print("Errors:")
                    print(result.stderr)
                return False
                
        except Exception as e:
            print(f"Error running infrastructure tests: {e}")
            return False
    
    def cleanup_test_resources(self, stack_name: str, template_bucket: str = None) -> bool:
        """Clean up test resources."""
        print(f"\nCleaning up test resources...")
        
        success = True
        
        # Delete CloudFormation stack
        try:
            if self._stack_exists(stack_name):
                print(f"Deleting stack: {stack_name}")
                delete_success = self.delete_stack(stack_name)
                if not delete_success:
                    success = False
            else:
                print(f"Stack {stack_name} does not exist")
        except Exception as e:
            print(f"Error deleting stack: {e}")
            success = False
        
        # Delete template bucket if provided
        if template_bucket:
            try:
                print(f"Deleting template bucket: {template_bucket}")
                
                # Delete all objects first
                objects_response = self.s3_client.list_objects_v2(Bucket=template_bucket)
                if 'Contents' in objects_response:
                    objects_to_delete = [{'Key': obj['Key']} for obj in objects_response['Contents']]
                    self.s3_client.delete_objects(
                        Bucket=template_bucket,
                        Delete={'Objects': objects_to_delete}
                    )
                
                # Delete bucket
                self.s3_client.delete_bucket(Bucket=template_bucket)
                print(f"✓ Template bucket deleted")
                
            except ClientError as e:
                print(f"Error deleting template bucket: {e}")
                success = False
        
        return success


def main():
    """Main test deployment function."""
    parser = argparse.ArgumentParser(description='Deploy and validate test infrastructure')
    parser.add_argument('--stack-name', default='zackspeakfitness-test', 
                       help='CloudFormation stack name for testing')
    parser.add_argument('--domain-name', default='test.zackspeakfitness.com',
                       help='Domain name for testing')
    parser.add_argument('--region', default='us-west-2', help='AWS region')
    parser.add_argument('--cleanup-only', action='store_true', 
                       help='Only clean up existing test resources')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Skip cleanup after testing')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate existing infrastructure')
    
    args = parser.parse_args()
    
    # Check AWS credentials
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        if not credentials:
            print("Error: AWS credentials not configured.")
            print("Please run 'aws configure' or set environment variables:")
            print("  export AWS_ACCESS_KEY_ID=your_access_key")
            print("  export AWS_SECRET_ACCESS_KEY=your_secret_key")
            print("  export AWS_DEFAULT_REGION=us-west-2")
            sys.exit(1)
    except Exception as e:
        print(f"Error checking AWS credentials: {e}")
        sys.exit(1)
    
    deployer = TestEnvironmentDeployer(region=args.region)
    
    # Handle cleanup only
    if args.cleanup_only:
        success = deployer.cleanup_test_resources(args.stack_name)
        sys.exit(0 if success else 1)
    
    # Handle validation only
    if args.validate_only:
        if not deployer._stack_exists(args.stack_name):
            print(f"Stack {args.stack_name} does not exist")
            sys.exit(1)
        
        # Validate resources
        resources_valid = deployer.validate_infrastructure_resources(args.stack_name)
        
        # Test HTTPS connectivity
        https_valid = deployer.test_https_connectivity(args.domain_name)
        
        # Run tests
        tests_valid = deployer.run_infrastructure_tests(args.stack_name)
        
        all_valid = resources_valid and https_valid and tests_valid
        
        print("\n" + "="*50)
        if all_valid:
            print("✓ All validation checks passed!")
        else:
            print("✗ Some validation checks failed!")
        
        sys.exit(0 if all_valid else 1)
    
    # Full deployment and validation
    print("Starting test environment deployment and validation...")
    print("="*60)
    
    template_bucket = None
    try:
        # Deploy test stack
        deployment_success = deployer.deploy_test_stack(args.stack_name, args.domain_name)
        
        if not deployment_success:
            print("Deployment failed, exiting...")
            sys.exit(1)
        
        # Get template bucket from stack outputs for cleanup
        outputs = deployer.get_stack_outputs(args.stack_name)
        
        # Validate infrastructure
        resources_valid = deployer.validate_infrastructure_resources(args.stack_name)
        
        # Test HTTPS connectivity (may fail if DNS hasn't propagated)
        print("\nNote: HTTPS connectivity test may fail if DNS hasn't fully propagated")
        https_valid = deployer.test_https_connectivity(args.domain_name)
        
        # Run infrastructure tests
        tests_valid = deployer.run_infrastructure_tests(args.stack_name)
        
        # Summary
        print("\n" + "="*60)
        print("DEPLOYMENT AND VALIDATION SUMMARY")
        print("="*60)
        
        results = [
            ("Stack Deployment", deployment_success),
            ("Resource Validation", resources_valid),
            ("HTTPS Connectivity", https_valid),
            ("Infrastructure Tests", tests_valid)
        ]
        
        all_successful = True
        for test_name, success in results:
            status = "✓ PASS" if success else "✗ FAIL"
            print(f"{test_name:.<30} {status}")
            if not success:
                all_successful = False
        
        print("="*60)
        
        if all_successful:
            print("🎉 All tests passed! Infrastructure is ready for production.")
        else:
            print("⚠️  Some tests failed. Please review the output above.")
        
        # Cleanup if requested
        if not args.no_cleanup:
            print("\nCleaning up test resources...")
            cleanup_success = deployer.cleanup_test_resources(args.stack_name, template_bucket)
            if cleanup_success:
                print("✓ Test resources cleaned up successfully")
            else:
                print("⚠️  Some cleanup operations failed")
        else:
            print(f"\nTest stack '{args.stack_name}' left running (use --cleanup-only to remove)")
        
        sys.exit(0 if all_successful else 1)
        
    except KeyboardInterrupt:
        print("\nDeployment interrupted by user")
        if template_bucket and not args.no_cleanup:
            print("Cleaning up...")
            deployer.cleanup_test_resources(args.stack_name, template_bucket)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        if template_bucket and not args.no_cleanup:
            print("Cleaning up...")
            deployer.cleanup_test_resources(args.stack_name, template_bucket)
        sys.exit(1)


if __name__ == '__main__':
    main()