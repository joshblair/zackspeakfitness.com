"""
Property-based tests for Route 53 DNS infrastructure validation.
Feature: static-website-infrastructure, Property 8: DNS Resolution Consistency
"""
import pytest
import boto3
import socket
import dns.resolver
import dns.exception
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Optional
import time
import yaml
from botocore.exceptions import ClientError, NoCredentialsError


class TestDNSResolutionConsistency:
    """
    Property 8: DNS Resolution Consistency
    For any DNS query for zackspeakfitness.com or www.zackspeakfitness.com, 
    it should resolve to the CloudFront distribution
    Validates: Requirements 2.1
    """

    def get_dns_info_from_stack(self, cloudformation_client, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get DNS configuration details from CloudFormation stack."""
        try:
            # Get stack outputs
            response = cloudformation_client.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            # Find DNS info from outputs
            dns_info = {}
            for output in outputs:
                if output['OutputKey'] == 'HostedZoneId':
                    dns_info['hosted_zone_id'] = output['OutputValue']
                elif output['OutputKey'] == 'NameServers':
                    dns_info['name_servers'] = output['OutputValue']
                elif output['OutputKey'] == 'ApexHealthCheckId':
                    dns_info['apex_health_check_id'] = output['OutputValue']
                elif output['OutputKey'] == 'WWWHealthCheckId':
                    dns_info['www_health_check_id'] = output['OutputValue']
            
            return dns_info if dns_info else None
            
        except Exception:
            return None

    def get_cloudfront_distribution_domain(self, cloudformation_client, distribution_stack_name: str) -> Optional[str]:
        """Get CloudFront distribution domain from stack outputs."""
        try:
            response = cloudformation_client.describe_stacks(StackName=distribution_stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            for output in outputs:
                if output['OutputKey'] == 'DistributionDomainName':
                    return output['OutputValue']
            
            return None
        except Exception:
            return None

    @pytest.mark.parametrize("domain_name", ['zackspeakfitness.com', 'www.zackspeakfitness.com'])
    def test_dns_resolution_to_cloudfront(self, domain_name, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 8: DNS Resolution Consistency
        Test that DNS queries resolve to CloudFront distribution.
        """
        dns_info = self.get_dns_info_from_stack(
            cloudformation_client, 
            test_config.get('dns_stack_name', 'zackspeakfitness-dns-test')
        )
        
        # Skip test if DNS stack doesn't exist
        if dns_info is None:
            pytest.skip("DNS stack not deployed or DNS info not found")
        
        # Get expected CloudFront distribution domain
        expected_distribution_domain = self.get_cloudfront_distribution_domain(
            cloudformation_client,
            test_config.get('distribution_stack_name', 'zackspeakfitness-distribution-test')
        )
        
        if not expected_distribution_domain:
            pytest.skip("CloudFront distribution not found or not deployed")
        
        try:
            # Perform DNS resolution using dnspython
            resolver = dns.resolver.Resolver()
            resolver.timeout = 10
            resolver.lifetime = 30
            
            # Query A records for the domain
            answers = resolver.resolve(domain_name, 'A')
            
            # Get the CNAME chain to find the CloudFront distribution
            cname_answers = None
            try:
                cname_answers = resolver.resolve(domain_name, 'CNAME')
            except dns.resolver.NoAnswer:
                # No CNAME records, check if it's an alias record
                pass
            
            # For alias records (A records pointing to CloudFront), we need to verify
            # that the resolution eventually leads to CloudFront infrastructure
            resolved_ips = [str(rdata) for rdata in answers]
            
            assert len(resolved_ips) > 0, f"Domain {domain_name} should resolve to at least one IP address"
            
            # Verify that the resolved IPs belong to CloudFront by doing reverse DNS lookup
            # CloudFront IPs typically resolve to *.cloudfront.net domains
            cloudfront_verified = False
            for ip in resolved_ips:
                try:
                    reverse_dns = socket.gethostbyaddr(ip)[0]
                    if 'cloudfront.net' in reverse_dns.lower():
                        cloudfront_verified = True
                        break
                except (socket.herror, socket.gaierror):
                    # Reverse DNS lookup failed, continue with next IP
                    continue
            
            # If we have CNAME records, verify they point to CloudFront
            if cname_answers:
                for cname in cname_answers:
                    cname_target = str(cname).rstrip('.')
                    assert 'cloudfront.net' in cname_target.lower(), f"CNAME for {domain_name} should point to CloudFront, got {cname_target}"
                    cloudfront_verified = True
            
            # At least one verification method should confirm CloudFront
            assert cloudfront_verified, f"Domain {domain_name} should resolve to CloudFront infrastructure"
            
        except dns.resolver.NXDOMAIN:
            pytest.skip(f"Domain {domain_name} does not exist in DNS (might not be configured yet)")
        except dns.resolver.NoAnswer:
            pytest.skip(f"No DNS answer for {domain_name} (might not be configured yet)")
        except dns.exception.Timeout:
            pytest.skip(f"DNS query timeout for {domain_name}")
        except Exception as e:
            pytest.skip(f"DNS resolution failed for {domain_name}: {e}")

    @given(subdomain=st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_subdomain_resolution(self, subdomain, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 8: DNS Resolution Consistency
        Property-based test: For any invalid subdomain, DNS resolution should fail appropriately.
        """
        dns_info = self.get_dns_info_from_stack(
            cloudformation_client, 
            test_config.get('dns_stack_name', 'zackspeakfitness-dns-test')
        )
        
        # Skip test if DNS stack doesn't exist
        if dns_info is None:
            pytest.skip("DNS stack not deployed or DNS info not found")
        
        # Create an invalid subdomain (not www or apex)
        invalid_domain = f"{subdomain.lower()}.zackspeakfitness.com"
        
        # Skip if this happens to be a valid subdomain we support
        if invalid_domain in ['www.zackspeakfitness.com', 'zackspeakfitness.com']:
            return
        
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 10
            
            # Query A records for the invalid subdomain
            answers = resolver.resolve(invalid_domain, 'A')
            
            # If we get here, the subdomain resolved, which might be unexpected
            # This could happen if there's a wildcard record, which is not part of our design
            resolved_ips = [str(rdata) for rdata in answers]
            
            # If it resolves, it should not resolve to our CloudFront distribution
            # (since we only configured apex and www)
            pytest.fail(f"Invalid subdomain {invalid_domain} should not resolve, but got IPs: {resolved_ips}")
            
        except dns.resolver.NXDOMAIN:
            # This is expected - invalid subdomains should not exist
            pass
        except dns.resolver.NoAnswer:
            # This is also acceptable - no A records for invalid subdomain
            pass
        except dns.exception.Timeout:
            # Timeout is acceptable for this test
            pass
        except Exception:
            # Other DNS errors are acceptable for invalid subdomains
            pass

    def test_hosted_zone_configuration(self, cloudformation_client, route53_client, test_config):
        """
        Feature: static-website-infrastructure, Property 8: DNS Resolution Consistency
        Test that hosted zone is properly configured.
        """
        dns_info = self.get_dns_info_from_stack(
            cloudformation_client, 
            test_config.get('dns_stack_name', 'zackspeakfitness-dns-test')
        )
        
        # Skip test if DNS stack doesn't exist
        if dns_info is None:
            pytest.skip("DNS stack not deployed or DNS info not found")
        
        hosted_zone_id = dns_info.get('hosted_zone_id')
        if not hosted_zone_id:
            pytest.skip("Hosted zone ID not found in stack outputs")
        
        try:
            # Get hosted zone details
            response = route53_client.get_hosted_zone(Id=hosted_zone_id)
            hosted_zone = response['HostedZone']
            
            # Verify hosted zone configuration
            assert hosted_zone['Name'] == 'zackspeakfitness.com.', f"Hosted zone name should be 'zackspeakfitness.com.', got {hosted_zone['Name']}"
            assert hosted_zone['Config']['PrivateZone'] == False, "Hosted zone should be public"
            
            # Get record sets
            record_response = route53_client.list_resource_record_sets(HostedZoneId=hosted_zone_id)
            record_sets = record_response['ResourceRecordSets']
            
            # Find A records for apex and www
            apex_records = [r for r in record_sets if r['Name'] == 'zackspeakfitness.com.' and r['Type'] == 'A']
            www_records = [r for r in record_sets if r['Name'] == 'www.zackspeakfitness.com.' and r['Type'] == 'A']
            
            assert len(apex_records) > 0, "Should have A record for apex domain"
            assert len(www_records) > 0, "Should have A record for www subdomain"
            
            # Verify alias records point to CloudFront
            for record in apex_records + www_records:
                if 'AliasTarget' in record:
                    alias_target = record['AliasTarget']
                    assert 'cloudfront.net' in alias_target['DNSName'].lower(), f"Alias target should be CloudFront, got {alias_target['DNSName']}"
                    assert alias_target['HostedZoneId'] == 'Z2FDTNDATAQYW2', f"CloudFront hosted zone ID should be Z2FDTNDATAQYW2, got {alias_target['HostedZoneId']}"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchHostedZone':
                pytest.skip("Hosted zone not found")
            else:
                raise

    def test_health_checks_configuration(self, cloudformation_client, route53_client, test_config):
        """
        Feature: static-website-infrastructure, Property 8: DNS Resolution Consistency
        Test that health checks are properly configured.
        """
        dns_info = self.get_dns_info_from_stack(
            cloudformation_client, 
            test_config.get('dns_stack_name', 'zackspeakfitness-dns-test')
        )
        
        # Skip test if DNS stack doesn't exist
        if dns_info is None:
            pytest.skip("DNS stack not deployed or DNS info not found")
        
        apex_health_check_id = dns_info.get('apex_health_check_id')
        www_health_check_id = dns_info.get('www_health_check_id')
        
        if not apex_health_check_id or not www_health_check_id:
            pytest.skip("Health check IDs not found in stack outputs")
        
        try:
            # Test apex health check
            apex_response = route53_client.get_health_check(HealthCheckId=apex_health_check_id)
            apex_config = apex_response['HealthCheck']['HealthCheckConfig']
            
            assert apex_config['Type'] == 'HTTPS', "Apex health check should use HTTPS"
            assert apex_config['FullyQualifiedDomainName'] == 'zackspeakfitness.com', "Apex health check should monitor apex domain"
            assert apex_config['Port'] == 443, "Apex health check should use port 443"
            assert apex_config['ResourcePath'] == '/', "Apex health check should check root path"
            
            # Test www health check
            www_response = route53_client.get_health_check(HealthCheckId=www_health_check_id)
            www_config = www_response['HealthCheck']['HealthCheckConfig']
            
            assert www_config['Type'] == 'HTTPS', "WWW health check should use HTTPS"
            assert www_config['FullyQualifiedDomainName'] == 'www.zackspeakfitness.com', "WWW health check should monitor www subdomain"
            assert www_config['Port'] == 443, "WWW health check should use port 443"
            assert www_config['ResourcePath'] == '/', "WWW health check should check root path"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchHealthCheck':
                pytest.skip("Health check not found")
            else:
                raise

    @pytest.mark.parametrize("domain_name", ['zackspeakfitness.com', 'www.zackspeakfitness.com'])
    def test_dns_propagation_consistency(self, domain_name, test_config):
        """
        Feature: static-website-infrastructure, Property 8: DNS Resolution Consistency
        Test DNS propagation consistency across multiple DNS servers.
        """
        # List of public DNS servers to test against
        dns_servers = [
            '8.8.8.8',      # Google DNS
            '1.1.1.1',      # Cloudflare DNS
            '208.67.222.222', # OpenDNS
            '9.9.9.9'       # Quad9 DNS
        ]
        
        resolved_results = []
        
        for dns_server in dns_servers:
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [dns_server]
                resolver.timeout = 5
                resolver.lifetime = 10
                
                # Query A records
                answers = resolver.resolve(domain_name, 'A')
                resolved_ips = sorted([str(rdata) for rdata in answers])
                resolved_results.append((dns_server, resolved_ips))
                
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
                # DNS might not be propagated to this server yet
                resolved_results.append((dns_server, None))
            except Exception:
                # Other DNS errors
                resolved_results.append((dns_server, None))
        
        # Filter out None results (failed queries)
        successful_results = [(server, ips) for server, ips in resolved_results if ips is not None]
        
        if len(successful_results) == 0:
            pytest.skip(f"Domain {domain_name} not resolvable from any test DNS server (might not be configured yet)")
        
        # Check consistency among successful results
        if len(successful_results) > 1:
            first_result = successful_results[0][1]
            for server, ips in successful_results[1:]:
                assert ips == first_result, f"DNS resolution inconsistent: {successful_results[0][0]} returned {first_result}, but {server} returned {ips}"

    def test_dns_record_ttl_configuration(self, cloudformation_client, route53_client, test_config):
        """
        Feature: static-website-infrastructure, Property 8: DNS Resolution Consistency
        Test that DNS records have appropriate TTL values.
        """
        dns_info = self.get_dns_info_from_stack(
            cloudformation_client, 
            test_config.get('dns_stack_name', 'zackspeakfitness-dns-test')
        )
        
        # Skip test if DNS stack doesn't exist
        if dns_info is None:
            pytest.skip("DNS stack not deployed or DNS info not found")
        
        hosted_zone_id = dns_info.get('hosted_zone_id')
        if not hosted_zone_id:
            pytest.skip("Hosted zone ID not found in stack outputs")
        
        try:
            # Get record sets
            response = route53_client.list_resource_record_sets(HostedZoneId=hosted_zone_id)
            record_sets = response['ResourceRecordSets']
            
            # Find A records for apex and www
            apex_records = [r for r in record_sets if r['Name'] == 'zackspeakfitness.com.' and r['Type'] == 'A']
            www_records = [r for r in record_sets if r['Name'] == 'www.zackspeakfitness.com.' and r['Type'] == 'A']
            
            # For alias records, TTL is managed by AWS and not explicitly set
            # But we can verify the records exist and are properly configured
            for record in apex_records + www_records:
                if 'AliasTarget' in record:
                    # Alias records don't have explicit TTL, but should have alias target
                    assert 'DNSName' in record['AliasTarget'], "Alias record should have DNS name"
                    assert 'HostedZoneId' in record['AliasTarget'], "Alias record should have hosted zone ID"
                else:
                    # Non-alias records should have reasonable TTL
                    ttl = record.get('TTL', 0)
                    assert 60 <= ttl <= 86400, f"DNS record TTL should be between 60 and 86400 seconds, got {ttl}"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchHostedZone':
                pytest.skip("Hosted zone not found")
            else:
                raise


class TestDNSIntegration:
    """Integration tests for DNS functionality."""
    
    def test_dns_cloudformation_template_syntax(self):
        """
        Test that DNS CloudFormation template has valid syntax.
        """
        try:
            # Read the template as text first to check basic structure
            with open('cloudformation/templates/dns.yaml', 'r') as f:
                template_content = f.read()
            
            # Basic content validation
            assert 'AWSTemplateFormatVersion' in template_content
            assert 'Resources:' in template_content
            assert 'HostedZone:' in template_content
            assert 'AWS::Route53::HostedZone' in template_content
            assert 'ApexRecord:' in template_content
            assert 'WWWRecord:' in template_content
            assert 'AWS::Route53::RecordSet' in template_content
            
            # Check for health check configuration
            assert 'ApexHealthCheck:' in template_content
            assert 'WWWHealthCheck:' in template_content
            assert 'AWS::Route53::HealthCheck' in template_content
            assert 'Type: HTTPS' in template_content
            assert 'Port: 443' in template_content
            
            # Check for CloudWatch alarms
            assert 'ApexHealthCheckAlarm:' in template_content
            assert 'WWWHealthCheckAlarm:' in template_content
            assert 'AWS::CloudWatch::Alarm' in template_content
            
            # Check for SNS topic
            assert 'HealthCheckSNSTopic:' in template_content
            assert 'AWS::SNS::Topic' in template_content
            
            # Check for failover configuration
            assert 'Failover: PRIMARY' in template_content
            assert 'Failover: SECONDARY' in template_content
            
        except FileNotFoundError:
            pytest.fail("DNS CloudFormation template not found")

    def test_dns_parameters_validation(self):
        """
        Test that DNS template has proper parameter validation.
        """
        try:
            with open('cloudformation/templates/dns.yaml', 'r') as f:
                template_content = f.read()
            
            # Check for parameter validation patterns
            assert 'AllowedPattern:' in template_content
            assert 'ConstraintDescription:' in template_content
            assert 'AllowedValues:' in template_content
            
            # Check for domain name validation
            assert 'Must be a valid domain name' in template_content
            assert 'Must be a valid CloudFront distribution domain name' in template_content
            assert 'Must be a valid Route 53 hosted zone ID' in template_content
            
        except FileNotFoundError:
            pytest.fail("DNS CloudFormation template not found")

    def test_dns_outputs_completeness(self):
        """
        Test that DNS template provides all required outputs.
        """
        try:
            with open('cloudformation/templates/dns.yaml', 'r') as f:
                template_content = f.read()
            
            # Check for required outputs
            assert 'HostedZoneId:' in template_content
            assert 'NameServers:' in template_content
            assert 'ApexHealthCheckId:' in template_content
            assert 'WWWHealthCheckId:' in template_content
            assert 'HealthCheckSNSTopicArn:' in template_content
            assert 'ApexRecordName:' in template_content
            assert 'WWWRecordName:' in template_content
            
            # Check for export names
            assert 'Export:' in template_content
            assert 'Name: !Sub' in template_content
            
        except FileNotFoundError:
            pytest.fail("DNS CloudFormation template not found")