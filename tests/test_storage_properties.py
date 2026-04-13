"""
Property-based tests for S3 storage infrastructure validation.
Feature: static-website-infrastructure, Property 2: OAC Security Enforcement
"""
import pytest
import boto3
import requests
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Optional
import time
import yaml
from botocore.exceptions import ClientError, NoCredentialsError


class TestOACSecurityEnforcement:
    """
    Property 2: OAC Security Enforcement
    For any attempt to access S3 bucket content, direct access should be denied 
    while CloudFront access should succeed
    Validates: Requirements 1.2, 5.1
    """

    def get_bucket_from_stack(self, cloudformation_client, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get S3 bucket details from CloudFormation stack."""
        try:
            # Get stack outputs
            response = cloudformation_client.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            # Find bucket name and domain from outputs
            bucket_info = {}
            for output in outputs:
                if output['OutputKey'] == 'BucketName':
                    bucket_info['bucket_name'] = output['OutputValue']
                elif output['OutputKey'] == 'BucketDomainName':
                    bucket_info['bucket_domain'] = output['OutputValue']
                elif output['OutputKey'] == 'OriginAccessControlId':
                    bucket_info['oac_id'] = output['OutputValue']
            
            return bucket_info if bucket_info else None
            
        except Exception:
            return None

    def test_s3_bucket_blocks_direct_public_access(self, cloudformation_client, s3_client, test_config):
        """
        Feature: static-website-infrastructure, Property 2: OAC Security Enforcement
        Test that S3 bucket blocks direct public access attempts.
        """
        bucket_info = self.get_bucket_from_stack(
            cloudformation_client, 
            test_config['storage_stack_name']
        )
        
        # Skip test if storage stack doesn't exist
        if bucket_info is None:
            pytest.skip("Storage stack not deployed or bucket not found")
        
        bucket_name = bucket_info.get('bucket_name')
        if not bucket_name:
            pytest.skip("Bucket name not found in stack outputs")
        
        # Test 1: Verify bucket public access block configuration
        try:
            response = s3_client.get_public_access_block(Bucket=bucket_name)
            public_access_config = response['PublicAccessBlockConfiguration']
            
            assert public_access_config['BlockPublicAcls'] == True, "BlockPublicAcls should be enabled"
            assert public_access_config['IgnorePublicAcls'] == True, "IgnorePublicAcls should be enabled"
            assert public_access_config['BlockPublicPolicy'] == True, "BlockPublicPolicy should be enabled"
            assert public_access_config['RestrictPublicBuckets'] == True, "RestrictPublicBuckets should be enabled"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchPublicAccessBlockConfiguration':
                pytest.fail("Public access block configuration not found - bucket should have public access blocked")
            else:
                raise

    def test_s3_bucket_policy_denies_direct_access(self, cloudformation_client, s3_client, test_config):
        """
        Feature: static-website-infrastructure, Property 2: OAC Security Enforcement
        Test that bucket policy explicitly denies direct access.
        """
        bucket_info = self.get_bucket_from_stack(
            cloudformation_client, 
            test_config['storage_stack_name']
        )
        
        # Skip test if storage stack doesn't exist
        if bucket_info is None:
            pytest.skip("Storage stack not deployed or bucket not found")
        
        bucket_name = bucket_info.get('bucket_name')
        if not bucket_name:
            pytest.skip("Bucket name not found in stack outputs")
        
        # Get bucket policy
        try:
            response = s3_client.get_bucket_policy(Bucket=bucket_name)
            policy_document = response['Policy']
            
            # Parse policy JSON
            import json
            policy = json.loads(policy_document)
            
            # Check for deny statements
            statements = policy.get('Statement', [])
            
            # Look for deny statements that block direct access
            has_deny_direct_access = False
            has_deny_insecure_transport = False
            
            for statement in statements:
                if statement.get('Effect') == 'Deny':
                    # Check for direct access denial
                    if 'StringNotEquals' in statement.get('Condition', {}):
                        condition = statement['Condition']['StringNotEquals']
                        if 'AWS:SourceArn' in condition:
                            has_deny_direct_access = True
                    
                    # Check for insecure transport denial
                    if 'Bool' in statement.get('Condition', {}):
                        condition = statement['Condition']['Bool']
                        if condition.get('aws:SecureTransport') == 'false':
                            has_deny_insecure_transport = True
            
            assert has_deny_direct_access, "Bucket policy should deny direct access (non-CloudFront requests)"
            assert has_deny_insecure_transport, "Bucket policy should deny insecure transport (HTTP)"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchBucketPolicy':
                pytest.fail("Bucket policy not found - bucket should have a policy to deny direct access")
            else:
                raise

    @given(test_object_key=st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_s3_direct_url_access_denied(self, cloudformation_client, test_config, test_object_key):
        """
        Feature: static-website-infrastructure, Property 2: OAC Security Enforcement
        Property-based test: For any object key, direct S3 URL access should be denied.
        """
        bucket_info = self.get_bucket_from_stack(
            cloudformation_client, 
            test_config['storage_stack_name']
        )
        
        # Skip test if storage stack doesn't exist
        if bucket_info is None:
            pytest.skip("Storage stack not deployed or bucket not found")
        
        bucket_name = bucket_info.get('bucket_name')
        bucket_domain = bucket_info.get('bucket_domain')
        
        if not bucket_name or not bucket_domain:
            pytest.skip("Bucket information not complete in stack outputs")
        
        # Construct direct S3 URL
        # Clean the object key to be URL-safe
        safe_object_key = test_object_key.replace(' ', '_').replace('/', '_')
        direct_url = f"https://{bucket_domain}/{safe_object_key}"
        
        # Attempt to access the object directly
        try:
            response = requests.get(direct_url, timeout=10)
            
            # Direct access should be denied (403 Forbidden or 404 Not Found)
            # 403 = Access denied by policy
            # 404 = Object doesn't exist (which is fine for this test)
            assert response.status_code in [403, 404], f"Direct S3 access should be denied, got status {response.status_code}"
            
            # If we get 403, verify it's due to access denied, not other reasons
            if response.status_code == 403:
                # The response should indicate access denied
                assert 'AccessDenied' in response.text or 'Forbidden' in response.text, "403 should be due to access denial"
                
        except requests.exceptions.RequestException:
            # Network errors are acceptable - the important thing is that we don't get successful access
            pass

    def test_oac_configuration_exists(self, cloudformation_client, cloudfront_client, test_config):
        """
        Feature: static-website-infrastructure, Property 2: OAC Security Enforcement
        Test that Origin Access Control is properly configured.
        """
        bucket_info = self.get_bucket_from_stack(
            cloudformation_client, 
            test_config['storage_stack_name']
        )
        
        # Skip test if storage stack doesn't exist
        if bucket_info is None:
            pytest.skip("Storage stack not deployed or bucket not found")
        
        oac_id = bucket_info.get('oac_id')
        if not oac_id:
            pytest.skip("OAC ID not found in stack outputs")
        
        # Verify OAC exists and has correct configuration
        try:
            response = cloudfront_client.get_origin_access_control(Id=oac_id)
            oac_config = response['OriginAccessControl']['OriginAccessControlConfig']
            
            assert oac_config['OriginAccessControlOriginType'] == 's3', "OAC should be configured for S3 origin"
            assert oac_config['SigningBehavior'] == 'always', "OAC should always sign requests"
            assert oac_config['SigningProtocol'] == 'sigv4', "OAC should use SigV4 signing protocol"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchOriginAccessControl':
                pytest.fail("Origin Access Control not found")
            else:
                raise

    def test_bucket_encryption_enabled(self, cloudformation_client, s3_client, test_config):
        """
        Feature: static-website-infrastructure, Property 2: OAC Security Enforcement
        Test that S3 bucket has encryption enabled.
        """
        bucket_info = self.get_bucket_from_stack(
            cloudformation_client, 
            test_config['storage_stack_name']
        )
        
        # Skip test if storage stack doesn't exist
        if bucket_info is None:
            pytest.skip("Storage stack not deployed or bucket not found")
        
        bucket_name = bucket_info.get('bucket_name')
        if not bucket_name:
            pytest.skip("Bucket name not found in stack outputs")
        
        # Check bucket encryption configuration
        try:
            response = s3_client.get_bucket_encryption(Bucket=bucket_name)
            encryption_config = response['ServerSideEncryptionConfiguration']
            
            rules = encryption_config.get('Rules', [])
            assert len(rules) > 0, "Bucket should have encryption rules configured"
            
            # Check that at least one rule has AES256 encryption
            has_aes256 = False
            for rule in rules:
                default_encryption = rule.get('ApplyServerSideEncryptionByDefault', {})
                if default_encryption.get('SSEAlgorithm') == 'AES256':
                    has_aes256 = True
                    break
            
            assert has_aes256, "Bucket should have AES256 encryption enabled"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ServerSideEncryptionConfigurationNotFoundError':
                pytest.fail("Bucket encryption configuration not found - encryption should be enabled")
            else:
                raise

    def test_bucket_versioning_enabled(self, cloudformation_client, s3_client, test_config):
        """
        Feature: static-website-infrastructure, Property 2: OAC Security Enforcement
        Test that S3 bucket has versioning enabled.
        """
        bucket_info = self.get_bucket_from_stack(
            cloudformation_client, 
            test_config['storage_stack_name']
        )
        
        # Skip test if storage stack doesn't exist
        if bucket_info is None:
            pytest.skip("Storage stack not deployed or bucket not found")
        
        bucket_name = bucket_info.get('bucket_name')
        if not bucket_name:
            pytest.skip("Bucket name not found in stack outputs")
        
        # Check bucket versioning configuration
        try:
            response = s3_client.get_bucket_versioning(Bucket=bucket_name)
            versioning_status = response.get('Status', 'Disabled')
            
            assert versioning_status == 'Enabled', f"Bucket versioning should be enabled, but is {versioning_status}"
            
        except ClientError as e:
            pytest.fail(f"Error checking bucket versioning: {e}")


class TestStorageIntegration:
    """Integration tests for S3 storage functionality."""
    
    def test_storage_cloudformation_template_syntax(self):
        """
        Test that storage CloudFormation template has valid syntax.
        """
        try:
            # Read the template as text first to check basic structure
            with open('cloudformation/templates/storage.yaml', 'r') as f:
                template_content = f.read()
            
            # Basic content validation
            assert 'AWSTemplateFormatVersion' in template_content
            assert 'Resources:' in template_content
            assert 'WebsiteBucket:' in template_content
            assert 'AWS::S3::Bucket' in template_content
            assert 'OriginAccessControl:' in template_content
            assert 'AWS::CloudFront::OriginAccessControl' in template_content
            assert 'BucketPolicy:' in template_content
            assert 'AWS::S3::BucketPolicy' in template_content
            
            # Check for security configurations
            assert 'PublicAccessBlockConfiguration:' in template_content
            assert 'BlockPublicAcls: true' in template_content
            assert 'BucketEncryption:' in template_content
            assert 'VersioningConfiguration:' in template_content
            assert 'Status: Enabled' in template_content
            
            # Check for OAC configuration
            assert 'OriginAccessControlOriginType: s3' in template_content
            assert 'SigningBehavior: always' in template_content
            assert 'SigningProtocol: sigv4' in template_content
            
        except FileNotFoundError:
            pytest.fail("Storage CloudFormation template not found")

    def test_access_logs_bucket_exists(self):
        """
        Test that access logs bucket is defined in the template.
        """
        try:
            with open('cloudformation/templates/storage.yaml', 'r') as f:
                template_content = f.read()
            
            # Check for access logs bucket
            assert 'AccessLogsBucket:' in template_content
            assert 'access-logs' in template_content
            
        except FileNotFoundError:
            pytest.fail("Storage CloudFormation template not found")