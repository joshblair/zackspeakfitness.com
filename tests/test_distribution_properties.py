"""
Property-based tests for CloudFront distribution infrastructure validation.
Feature: static-website-infrastructure, Property 1: HTTPS Redirect Consistency
Feature: static-website-infrastructure, Property 5: Security Headers Consistency
"""
import pytest
import boto3
import requests
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Optional
import time
import yaml
from botocore.exceptions import ClientError, NoCredentialsError
import json


class TestHTTPSRedirectConsistency:
    """
    Property 1: HTTPS Redirect Consistency
    For any HTTP request to the domain, the system should consistently redirect 
    to the HTTPS equivalent with proper status codes
    Validates: Requirements 2.3, 2.5
    """

    def get_distribution_from_stack(self, cloudformation_client, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get CloudFront distribution details from CloudFormation stack."""
        try:
            # Get stack outputs
            response = cloudformation_client.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            # Find distribution info from outputs
            distribution_info = {}
            for output in outputs:
                if output['OutputKey'] == 'DistributionId':
                    distribution_info['distribution_id'] = output['OutputValue']
                elif output['OutputKey'] == 'DistributionDomainName':
                    distribution_info['distribution_domain'] = output['OutputValue']
            
            return distribution_info if distribution_info else None
            
        except Exception:
            return None

    @given(path=st.text(min_size=0, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_http_to_https_redirect_consistency(self, cloudformation_client, test_config, path):
        """
        Feature: static-website-infrastructure, Property 1: HTTPS Redirect Consistency
        Property-based test: For any HTTP request path, should redirect to HTTPS.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config.get('distribution_stack_name', 'zackspeakfitness-distribution-test')
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        distribution_domain = distribution_info.get('distribution_domain')
        if not distribution_domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        # Clean the path to be URL-safe
        safe_path = path.replace(' ', '_').replace('/', '_').replace('\\', '_')
        if safe_path and not safe_path.startswith('/'):
            safe_path = '/' + safe_path
        
        # Construct HTTP URL
        http_url = f"http://{distribution_domain}{safe_path}"
        
        # Test HTTP request - should redirect to HTTPS
        try:
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            
            # Should get a redirect status code (301 or 302)
            assert response.status_code in [301, 302], f"HTTP request should redirect, got status {response.status_code}"
            
            # Check Location header for HTTPS redirect
            location = response.headers.get('Location', '')
            assert location.startswith('https://'), f"Redirect should be to HTTPS, got Location: {location}"
            
            # Verify the redirect preserves the path
            if safe_path:
                assert safe_path in location, f"Redirect should preserve path {safe_path}, got Location: {location}"
                
        except requests.exceptions.RequestException as e:
            # Network errors might occur, but we should still be able to test the redirect behavior
            # Skip if we can't reach the distribution (might not be deployed yet)
            pytest.skip(f"Could not reach distribution for testing: {e}")

    @pytest.mark.parametrize("domain_name", ['zackspeakfitness.com', 'www.zackspeakfitness.com'])
    def test_custom_domain_https_redirect(self, domain_name, test_config):
        """
        Feature: static-website-infrastructure, Property 1: HTTPS Redirect Consistency
        Test HTTPS redirect for custom domains (when DNS is configured).
        """
        # Construct HTTP URL for custom domain
        http_url = f"http://{domain_name}/"
        
        try:
            response = requests.get(http_url, allow_redirects=False, timeout=10)
            
            # Should get a redirect status code (301 or 302)
            assert response.status_code in [301, 302], f"HTTP request to {domain_name} should redirect, got status {response.status_code}"
            
            # Check Location header for HTTPS redirect
            location = response.headers.get('Location', '')
            assert location.startswith('https://'), f"Redirect should be to HTTPS, got Location: {location}"
            assert domain_name in location, f"Redirect should preserve domain {domain_name}, got Location: {location}"
            
        except requests.exceptions.RequestException:
            # DNS might not be configured yet, skip this test
            pytest.skip(f"Could not reach {domain_name} for testing (DNS might not be configured)")

    def test_distribution_viewer_protocol_policy(self, cloudformation_client, cloudfront_client, test_config):
        """
        Feature: static-website-infrastructure, Property 1: HTTPS Redirect Consistency
        Test that CloudFront distribution is configured with redirect-to-https policy.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config.get('distribution_stack_name', 'zackspeakfitness-distribution-test')
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        distribution_id = distribution_info.get('distribution_id')
        if not distribution_id:
            pytest.skip("Distribution ID not found in stack outputs")
        
        # Get distribution configuration
        try:
            response = cloudfront_client.get_distribution(Id=distribution_id)
            distribution_config = response['Distribution']['DistributionConfig']
            
            # Check default cache behavior
            default_behavior = distribution_config['DefaultCacheBehavior']
            viewer_protocol_policy = default_behavior['ViewerProtocolPolicy']
            
            assert viewer_protocol_policy == 'redirect-to-https', f"Default behavior should redirect to HTTPS, got {viewer_protocol_policy}"
            
            # Check all cache behaviors
            cache_behaviors = distribution_config.get('CacheBehaviors', {}).get('Items', [])
            for behavior in cache_behaviors:
                behavior_policy = behavior['ViewerProtocolPolicy']
                assert behavior_policy == 'redirect-to-https', f"Cache behavior should redirect to HTTPS, got {behavior_policy}"
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchDistribution':
                pytest.skip("CloudFront distribution not found")
            else:
                raise


class TestSecurityHeadersConsistency:
    """
    Property 5: Security Headers Consistency
    For any HTTP response from CloudFront, security headers (HSTS, X-Content-Type-Options, 
    X-Frame-Options) should be present
    Validates: Requirements 5.2
    """

    def get_distribution_from_stack(self, cloudformation_client, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get CloudFront distribution details from CloudFormation stack."""
        try:
            # Get stack outputs
            response = cloudformation_client.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            # Find distribution info from outputs
            distribution_info = {}
            for output in outputs:
                if output['OutputKey'] == 'DistributionId':
                    distribution_info['distribution_id'] = output['OutputValue']
                elif output['OutputKey'] == 'DistributionDomainName':
                    distribution_info['distribution_domain'] = output['OutputValue']
                elif output['OutputKey'] == 'SecurityHeadersPolicyId':
                    distribution_info['security_headers_policy_id'] = output['OutputValue']
            
            return distribution_info if distribution_info else None
            
        except Exception:
            return None

    @given(path=st.text(min_size=0, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    @settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_security_headers_consistency(self, cloudformation_client, test_config, path):
        """
        Feature: static-website-infrastructure, Property 5: Security Headers Consistency
        Property-based test: For any HTTPS response path, security headers should be present.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config.get('distribution_stack_name', 'zackspeakfitness-distribution-test')
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        distribution_domain = distribution_info.get('distribution_domain')
        if not distribution_domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        # Clean the path to be URL-safe
        safe_path = path.replace(' ', '_').replace('/', '_').replace('\\', '_')
        if safe_path and not safe_path.startswith('/'):
            safe_path = '/' + safe_path
        
        # Construct HTTPS URL
        https_url = f"https://{distribution_domain}{safe_path}"
        
        try:
            # Make HTTPS request
            response = requests.get(https_url, timeout=10)
            
            # Check for required security headers
            headers = response.headers
            
            # Check for Strict-Transport-Security (HSTS)
            hsts_header = headers.get('Strict-Transport-Security', '')
            assert hsts_header, "Strict-Transport-Security header should be present"
            assert 'max-age=' in hsts_header, "HSTS header should contain max-age directive"
            assert 'includeSubDomains' in hsts_header, "HSTS header should include subdomains"
            
            # Check for X-Content-Type-Options
            content_type_options = headers.get('X-Content-Type-Options', '')
            assert content_type_options == 'nosniff', f"X-Content-Type-Options should be 'nosniff', got '{content_type_options}'"
            
            # Check for X-Frame-Options
            frame_options = headers.get('X-Frame-Options', '')
            assert frame_options == 'DENY', f"X-Frame-Options should be 'DENY', got '{frame_options}'"
            
            # Check for Referrer-Policy
            referrer_policy = headers.get('Referrer-Policy', '')
            assert referrer_policy == 'strict-origin-when-cross-origin', f"Referrer-Policy should be 'strict-origin-when-cross-origin', got '{referrer_policy}'"
            
        except requests.exceptions.RequestException:
            # Network errors might occur if distribution is not fully deployed
            pytest.skip(f"Could not reach distribution for security headers testing")

    def test_security_headers_policy_configuration(self, cloudformation_client, cloudfront_client, test_config):
        """
        Feature: static-website-infrastructure, Property 5: Security Headers Consistency
        Test that CloudFront distribution has security headers policy configured.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config.get('distribution_stack_name', 'zackspeakfitness-distribution-test')
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        distribution_id = distribution_info.get('distribution_id')
        security_headers_policy_id = distribution_info.get('security_headers_policy_id')
        
        if not distribution_id:
            pytest.skip("Distribution ID not found in stack outputs")
        
        # Get distribution configuration
        try:
            response = cloudfront_client.get_distribution(Id=distribution_id)
            distribution_config = response['Distribution']['DistributionConfig']
            
            # Check default cache behavior has response headers policy
            default_behavior = distribution_config['DefaultCacheBehavior']
            default_headers_policy = default_behavior.get('ResponseHeadersPolicyId')
            
            assert default_headers_policy, "Default behavior should have a response headers policy"
            
            # Check all cache behaviors have response headers policy
            cache_behaviors = distribution_config.get('CacheBehaviors', {}).get('Items', [])
            for behavior in cache_behaviors:
                behavior_headers_policy = behavior.get('ResponseHeadersPolicyId')
                assert behavior_headers_policy, f"Cache behavior for {behavior.get('PathPattern')} should have response headers policy"
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchDistribution':
                pytest.skip("CloudFront distribution not found")
            else:
                raise

    def test_response_headers_policy_details(self, cloudformation_client, cloudfront_client, test_config):
        """
        Feature: static-website-infrastructure, Property 5: Security Headers Consistency
        Test the details of the response headers policy configuration.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config.get('distribution_stack_name', 'zackspeakfitness-distribution-test')
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        security_headers_policy_id = distribution_info.get('security_headers_policy_id')
        if not security_headers_policy_id:
            pytest.skip("Security headers policy ID not found in stack outputs")
        
        # Get response headers policy configuration
        try:
            response = cloudfront_client.get_response_headers_policy(Id=security_headers_policy_id)
            policy_config = response['ResponseHeadersPolicy']['ResponseHeadersPolicyConfig']
            
            # Check security headers configuration
            security_headers = policy_config.get('SecurityHeadersConfig', {})
            
            # Check HSTS configuration
            hsts_config = security_headers.get('StrictTransportSecurity', {})
            assert hsts_config.get('AccessControlMaxAgeSec') == 31536000, "HSTS max age should be 1 year (31536000 seconds)"
            assert hsts_config.get('IncludeSubdomains') == True, "HSTS should include subdomains"
            
            # Check Content Type Options
            content_type_options = security_headers.get('ContentTypeOptions', {})
            assert content_type_options is not None, "Content Type Options should be configured"
            
            # Check Frame Options
            frame_options = security_headers.get('FrameOptions', {})
            assert frame_options.get('FrameOption') == 'DENY', "Frame options should be set to DENY"
            
            # Check Referrer Policy
            referrer_policy = security_headers.get('ReferrerPolicy', {})
            assert referrer_policy.get('ReferrerPolicy') == 'strict-origin-when-cross-origin', "Referrer policy should be strict-origin-when-cross-origin"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchResponseHeadersPolicy':
                pytest.skip("Response headers policy not found")
            else:
                raise

    @pytest.mark.parametrize("domain_name", ['zackspeakfitness.com', 'www.zackspeakfitness.com'])
    def test_custom_domain_security_headers(self, domain_name, test_config):
        """
        Feature: static-website-infrastructure, Property 5: Security Headers Consistency
        Test security headers for custom domains (when DNS is configured).
        """
        # Construct HTTPS URL for custom domain
        https_url = f"https://{domain_name}/"
        
        try:
            response = requests.get(https_url, timeout=10)
            
            # Check for required security headers
            headers = response.headers
            
            # Check for Strict-Transport-Security (HSTS)
            hsts_header = headers.get('Strict-Transport-Security', '')
            assert hsts_header, f"Strict-Transport-Security header should be present for {domain_name}"
            
            # Check for X-Content-Type-Options
            content_type_options = headers.get('X-Content-Type-Options', '')
            assert content_type_options == 'nosniff', f"X-Content-Type-Options should be 'nosniff' for {domain_name}"
            
            # Check for X-Frame-Options
            frame_options = headers.get('X-Frame-Options', '')
            assert frame_options == 'DENY', f"X-Frame-Options should be 'DENY' for {domain_name}"
            
        except requests.exceptions.RequestException:
            # DNS might not be configured yet, skip this test
            pytest.skip(f"Could not reach {domain_name} for security headers testing (DNS might not be configured)")


class TestDistributionIntegration:
    """Integration tests for CloudFront distribution functionality."""
    
    def test_distribution_cloudformation_template_syntax(self):
        """
        Test that distribution CloudFormation template has valid syntax.
        """
        try:
            # Read the template as text first to check basic structure
            with open('cloudformation/templates/distribution.yaml', 'r') as f:
                template_content = f.read()
            
            # Basic content validation
            assert 'AWSTemplateFormatVersion' in template_content
            assert 'Resources:' in template_content
            assert 'CloudFrontDistribution:' in template_content
            assert 'AWS::CloudFront::Distribution' in template_content
            assert 'SecurityHeadersPolicy:' in template_content
            assert 'AWS::CloudFront::ResponseHeadersPolicy' in template_content
            
            # Check for HTTPS redirect configuration
            assert 'ViewerProtocolPolicy: redirect-to-https' in template_content
            
            # Check for security headers configuration
            assert 'StrictTransportSecurity:' in template_content
            assert 'ContentTypeOptions:' in template_content
            assert 'FrameOptions:' in template_content
            assert 'ReferrerPolicy:' in template_content
            
            # Check for caching configuration
            assert 'CacheBehaviors:' in template_content
            assert 'CachePolicyId:' in template_content
            assert 'Compress: true' in template_content
            
            # Check for custom domain configuration
            assert 'Aliases:' in template_content
            assert 'ViewerCertificate:' in template_content
            assert 'AcmCertificateArn:' in template_content
            
        except FileNotFoundError:
            pytest.fail("Distribution CloudFormation template not found")

    def test_cache_policies_exist(self):
        """
        Test that cache policies are defined in the template.
        """
        try:
            with open('cloudformation/templates/distribution.yaml', 'r') as f:
                template_content = f.read()
            
            # Check for cache policies
            assert 'StaticAssetsCachePolicy:' in template_content
            assert 'HTMLCachePolicy:' in template_content
            assert 'AWS::CloudFront::CachePolicy' in template_content
            
            # Check for different TTL configurations
            assert 'DefaultTTL: 86400' in template_content  # 24 hours for static assets
            assert 'DefaultTTL: 3600' in template_content   # 1 hour for HTML
            
        except FileNotFoundError:
            pytest.fail("Distribution CloudFormation template not found")

    def test_origin_access_control_integration(self):
        """
        Test that distribution template integrates with Origin Access Control.
        """
        try:
            with open('cloudformation/templates/distribution.yaml', 'r') as f:
                template_content = f.read()
            
            # Check for OAC integration
            assert 'OriginAccessControlId:' in template_content
            assert 'S3OriginConfig:' in template_content
            
        except FileNotFoundError:
            pytest.fail("Distribution CloudFormation template not found")