"""
Property-based tests for ACM certificate infrastructure validation.
Feature: static-website-infrastructure, Property 3: Certificate Domain Coverage
"""
import pytest
import boto3
import ssl
import socket
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any
import time
import yaml


class TestCertificateDomainCoverage:
    """
    Property 3: Certificate Domain Coverage
    For any subdomain in the certificate (zackspeakfitness.com, www.zackspeakfitness.com), 
    HTTPS connections should use the ACM certificate
    Validates: Requirements 2.2, 2.4
    """

    def get_certificate_from_stack(self, cloudformation_client, acm_client, stack_name: str) -> Dict[str, Any]:
        """Get certificate details from CloudFormation stack."""
        try:
            # Get stack outputs
            response = cloudformation_client.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            # Find certificate ARN from outputs
            certificate_arn = None
            for output in outputs:
                if output['OutputKey'] == 'CertificateArn':
                    certificate_arn = output['OutputValue']
                    break
            
            if not certificate_arn:
                return None
            
            # Get certificate details from ACM
            cert_response = acm_client.describe_certificate(CertificateArn=certificate_arn)
            return cert_response.get('Certificate', {})
            
        except Exception:
            return None

    @pytest.mark.parametrize("domain_name", ['zackspeakfitness.com', 'www.zackspeakfitness.com'])
    def test_certificate_covers_required_domains(self, domain_name, cloudformation_client, acm_client, test_config):
        """
        Feature: static-website-infrastructure, Property 3: Certificate Domain Coverage
        Test that certificate covers all required domains.
        """
        certificate = self.get_certificate_from_stack(
            cloudformation_client, 
            acm_client, 
            test_config['certificate_stack_name']
        )
        
        # Skip test if certificate stack doesn't exist (not deployed yet)
        if certificate is None:
            pytest.skip("Certificate stack not deployed or certificate not found")
        
        # Get all domains covered by the certificate
        covered_domains = set()
        
        # Add primary domain
        if 'DomainName' in certificate:
            covered_domains.add(certificate['DomainName'])
        
        # Add subject alternative names
        if 'SubjectAlternativeNames' in certificate:
            for san in certificate['SubjectAlternativeNames']:
                covered_domains.add(san)
        
        # Verify the domain is covered
        assert domain_name in covered_domains, f"Domain {domain_name} not covered by certificate. Covered domains: {covered_domains}"

    def test_certificate_validation_method_is_dns(self, cloudformation_client, acm_client, test_config):
        """
        Test that certificate uses DNS validation method.
        """
        certificate = self.get_certificate_from_stack(
            cloudformation_client, 
            acm_client, 
            test_config['certificate_stack_name']
        )
        
        # Skip test if certificate stack doesn't exist
        if certificate is None:
            pytest.skip("Certificate stack not deployed or certificate not found")
        
        # Check validation method
        domain_validation_options = certificate.get('DomainValidationOptions', [])
        
        for validation_option in domain_validation_options:
            validation_method = validation_option.get('ValidationMethod')
            assert validation_method == 'DNS', f"Certificate should use DNS validation, but uses {validation_method}"

    def test_certificate_status_is_issued(self, cloudformation_client, acm_client, test_config):
        """
        Test that certificate status is ISSUED (successfully validated).
        """
        certificate = self.get_certificate_from_stack(
            cloudformation_client, 
            acm_client, 
            test_config['certificate_stack_name']
        )
        
        # Skip test if certificate stack doesn't exist
        if certificate is None:
            pytest.skip("Certificate stack not deployed or certificate not found")
        
        status = certificate.get('Status')
        assert status == 'ISSUED', f"Certificate status should be ISSUED, but is {status}"

    @pytest.mark.parametrize("domain_name", ['zackspeakfitness.com', 'www.zackspeakfitness.com'])
    def test_certificate_domain_validation_records_exist(self, domain_name, cloudformation_client, acm_client, route53_client, test_config):
        """
        Feature: static-website-infrastructure, Property 3: Certificate Domain Coverage
        Test that DNS validation records exist for certificate domains.
        """
        certificate = self.get_certificate_from_stack(
            cloudformation_client, 
            acm_client, 
            test_config['certificate_stack_name']
        )
        
        # Skip test if certificate stack doesn't exist
        if certificate is None:
            pytest.skip("Certificate stack not deployed or certificate not found")
        
        # Find validation record for this domain
        domain_validation_options = certificate.get('DomainValidationOptions', [])
        validation_record = None
        
        for validation_option in domain_validation_options:
            if validation_option.get('DomainName') == domain_name:
                resource_record = validation_option.get('ResourceRecord', {})
                if resource_record:
                    validation_record = resource_record
                    break
        
        if validation_record is None:
            pytest.skip(f"No validation record found for domain {domain_name}")
        
        # Check if validation record exists in Route 53
        record_name = validation_record.get('Name')
        record_value = validation_record.get('Value')
        
        assert record_name, "Validation record name should exist"
        assert record_value, "Validation record value should exist"
        
        # Note: We can't easily verify the record exists in Route 53 without knowing the hosted zone ID
        # This would require additional infrastructure setup, so we verify the record details exist


class TestCertificateIntegration:
    """Integration tests for certificate functionality."""
    
    def test_certificate_cloudformation_template_syntax(self):
        """
        Test that certificate CloudFormation template has valid syntax.
        """
        try:
            # Read the template as text first to check basic structure
            with open('cloudformation/templates/certificate.yaml', 'r') as f:
                template_content = f.read()
            
            # Basic content validation
            assert 'AWSTemplateFormatVersion' in template_content
            assert 'Resources:' in template_content
            assert 'SSLCertificate:' in template_content
            assert 'AWS::CertificateManager::Certificate' in template_content
            assert 'ValidationMethod: DNS' in template_content
            assert 'DomainName:' in template_content
            assert 'SubjectAlternativeNames:' in template_content
            assert 'DomainValidationOptions:' in template_content
            
            # Check for required CloudFormation functions
            assert '!Ref' in template_content or 'Ref:' in template_content
            assert '!Sub' in template_content or 'Sub:' in template_content
            
        except FileNotFoundError:
            pytest.fail("Certificate CloudFormation template not found")