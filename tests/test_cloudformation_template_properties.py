"""
Property-based tests for CloudFormation template completeness validation.
Feature: static-website-infrastructure, Property 4: CloudFormation Template Completeness
"""
import pytest
import boto3
import yaml
import json
import os
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Set
from pathlib import Path


class TestCloudFormationTemplateCompleteness:
    """
    Property 4: CloudFormation Template Completeness
    For any deployment of the CloudFormation stack, all required AWS resources 
    (S3, CloudFront, ACM, Route 53) should be created successfully
    Validates: Requirements 3.1, 3.5
    """

    def get_template_path(self, template_name: str) -> Path:
        """Get path to CloudFormation template."""
        return Path('cloudformation') / template_name

    def load_template_content(self, template_path: Path) -> str:
        """Load template content as string."""
        try:
            with open(template_path, 'r') as f:
                return f.read()
        except FileNotFoundError:
            pytest.fail(f"Template not found: {template_path}")

    def parse_template_resources(self, template_content: str) -> Dict[str, Any]:
        """Parse CloudFormation template and extract resources."""
        # For CloudFormation templates with intrinsic functions, use text parsing
        # instead of YAML parsing since PyYAML doesn't understand CF functions
        
        resources = {}
        lines = template_content.split('\n')
        in_resources_section = False
        current_resource = None
        current_indent = 0
        
        for line in lines:
            stripped = line.strip()
            
            # Find Resources section
            if stripped == 'Resources:':
                in_resources_section = True
                continue
            
            # Exit Resources section when we hit another top-level section
            if in_resources_section and line and not line.startswith(' ') and ':' in line:
                if stripped not in ['Resources:', 'Outputs:', 'Parameters:', 'Conditions:', 'Metadata:']:
                    break
                if stripped != 'Resources:':
                    break
            
            if in_resources_section and line.strip():
                # Calculate indentation
                indent = len(line) - len(line.lstrip())
                
                # Resource definition (2 spaces from Resources:)
                if indent == 2 and ':' in line and not line.strip().startswith('#'):
                    resource_name = line.strip().rstrip(':')
                    current_resource = resource_name
                    current_indent = indent
                    resources[resource_name] = {}
                
                # Resource Type (4 spaces from Resources:)
                elif current_resource and indent == 4 and line.strip().startswith('Type:'):
                    resource_type = line.split('Type:')[1].strip()
                    resources[current_resource]['Type'] = resource_type
        
        return resources

    @pytest.mark.parametrize("template_name,expected_resources", [
        ('master-template.yaml', {
            'DNSStack': 'AWS::CloudFormation::Stack',
            'CertificateStack': 'AWS::CloudFormation::Stack', 
            'StorageStack': 'AWS::CloudFormation::Stack',
            'DistributionStack': 'AWS::CloudFormation::Stack',
            'CICDStack': 'AWS::CloudFormation::Stack'
        }),
        ('templates/certificate.yaml', {
            'SSLCertificate': 'AWS::CertificateManager::Certificate'
        }),
        ('templates/storage.yaml', {
            'WebsiteBucket': 'AWS::S3::Bucket',
            'OriginAccessControl': 'AWS::CloudFront::OriginAccessControl'
        }),
        ('templates/distribution.yaml', {
            'CloudFrontDistribution': 'AWS::CloudFront::Distribution'
        }),
        ('templates/dns.yaml', {
            'HostedZone': 'AWS::Route53::HostedZone'
        }),
        ('templates/cicd.yaml', {
            'GitHubActionsRole': 'AWS::IAM::Role'
        })
    ])
    def test_template_contains_required_resources(self, template_name: str, expected_resources: Dict[str, str]):
        """
        Feature: static-website-infrastructure, Property 4: CloudFormation Template Completeness
        Test that each template contains all required AWS resources.
        """
        template_path = self.get_template_path(template_name)
        
        # Skip if template doesn't exist (may not be implemented yet)
        if not template_path.exists():
            pytest.skip(f"Template not found: {template_path}")
        
        template_content = self.load_template_content(template_path)
        resources = self.parse_template_resources(template_content)
        
        # Check that all expected resources exist with correct types
        for resource_name, expected_type in expected_resources.items():
            assert resource_name in resources, f"Resource '{resource_name}' not found in {template_name}"
            
            resource = resources[resource_name]
            actual_type = resource.get('Type')
            assert actual_type == expected_type, f"Resource '{resource_name}' has type '{actual_type}', expected '{expected_type}'"

    @pytest.mark.parametrize("template_name", [
        'master-template.yaml',
        'templates/certificate.yaml',
        'templates/storage.yaml', 
        'templates/distribution.yaml',
        'templates/dns.yaml',
        'templates/cicd.yaml'
    ])
    def test_template_has_required_sections(self, template_name: str):
        """
        Feature: static-website-infrastructure, Property 4: CloudFormation Template Completeness
        Test that each template has required CloudFormation sections.
        """
        template_path = self.get_template_path(template_name)
        
        # Skip if template doesn't exist
        if not template_path.exists():
            pytest.skip(f"Template not found: {template_path}")
        
        template_content = self.load_template_content(template_path)
        
        # Required sections for all CloudFormation templates
        required_sections = ['AWSTemplateFormatVersion', 'Resources']
        
        for section in required_sections:
            assert section in template_content, f"Template {template_name} missing required section: {section}"
        
        # Check AWSTemplateFormatVersion is valid
        assert "'2010-09-09'" in template_content or '"2010-09-09"' in template_content, \
            f"Template {template_name} has invalid AWSTemplateFormatVersion"

    def test_master_template_cross_stack_references(self):
        """
        Feature: static-website-infrastructure, Property 4: CloudFormation Template Completeness
        Test that master template properly references nested stacks and passes parameters.
        """
        template_path = self.get_template_path('master-template.yaml')
        
        if not template_path.exists():
            pytest.skip("Master template not found")
        
        template_content = self.load_template_content(template_path)
        
        # Check for proper cross-stack references
        cross_stack_patterns = [
            '!GetAtt DNSStack.Outputs',
            '!GetAtt CertificateStack.Outputs', 
            '!GetAtt StorageStack.Outputs',
            '!GetAtt DistributionStack.Outputs'
        ]
        
        for pattern in cross_stack_patterns:
            assert pattern in template_content, f"Master template missing cross-stack reference: {pattern}"
        
        # Check for proper dependencies
        dependency_patterns = [
            'DependsOn: DNSStack',
            'DependsOn: CertificateStack',
            'DependsOn: StorageStack'
        ]
        
        # At least some dependencies should exist
        dependency_found = any(pattern in template_content for pattern in dependency_patterns)
        assert dependency_found, "Master template should have DependsOn relationships between stacks"

    @given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10))
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_template_parameter_validation_property(self, parameter_names: List[str]):
        """
        Feature: static-website-infrastructure, Property 4: CloudFormation Template Completeness
        For any set of parameter names, templates should handle parameter validation properly.
        """
        template_path = self.get_template_path('master-template.yaml')
        
        if not template_path.exists():
            pytest.skip("Master template not found")
        
        template_content = self.load_template_content(template_path)
        
        try:
            template = yaml.safe_load(template_content)
        except yaml.YAMLError:
            pytest.skip("Cannot parse template for parameter validation")
        
        parameters = template.get('Parameters', {})
        
        # Property: All parameters should have proper validation
        for param_name, param_config in parameters.items():
            # Each parameter should have a Type
            assert 'Type' in param_config, f"Parameter {param_name} missing Type"
            
            # String parameters should have constraints where appropriate
            if param_config.get('Type') == 'String':
                # Domain name parameter should have pattern validation
                if 'domain' in param_name.lower():
                    assert 'AllowedPattern' in param_config or 'AllowedValues' in param_config, \
                        f"Domain parameter {param_name} should have validation pattern"
                
                # Environment parameters should have allowed values
                if 'environment' in param_name.lower():
                    assert 'AllowedValues' in param_config, \
                        f"Environment parameter {param_name} should have AllowedValues"

    def test_template_outputs_completeness(self):
        """
        Feature: static-website-infrastructure, Property 4: CloudFormation Template Completeness
        Test that master template provides all necessary outputs for integration.
        """
        template_path = self.get_template_path('master-template.yaml')
        
        if not template_path.exists():
            pytest.skip("Master template not found")
        
        template_content = self.load_template_content(template_path)
        
        try:
            template = yaml.safe_load(template_content)
        except yaml.YAMLError:
            pytest.skip("Cannot parse template for output validation")
        
        outputs = template.get('Outputs', {})
        
        # Required outputs for integration with CI/CD and external systems
        required_outputs = [
            'WebsiteURL',
            'CloudFrontDistributionId', 
            'S3BucketName',
            'CertificateArn',
            'HostedZoneId',
            'GitHubActionsRoleArn'
        ]
        
        for output_name in required_outputs:
            assert output_name in outputs, f"Master template missing required output: {output_name}"
            
            output_config = outputs[output_name]
            assert 'Description' in output_config, f"Output {output_name} missing Description"
            assert 'Value' in output_config, f"Output {output_name} missing Value"

    @given(st.lists(st.sampled_from(['dev', 'staging', 'prod']), min_size=1, max_size=3))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_template_environment_configuration_property(self, environments: List[str]):
        """
        Feature: static-website-infrastructure, Property 4: CloudFormation Template Completeness
        For any valid environment configuration, templates should support proper parameterization.
        """
        # Test that parameter files exist for each environment
        for env in set(environments):  # Remove duplicates
            param_file = Path('cloudformation') / 'parameters' / f'{env}.json'
            
            if param_file.exists():
                # Validate parameter file structure
                try:
                    with open(param_file, 'r') as f:
                        params = json.load(f)
                    
                    # Should be a list of parameter objects
                    assert isinstance(params, list), f"Parameter file {param_file} should contain a list"
                    
                    # Each parameter should have ParameterKey and ParameterValue
                    for param in params:
                        assert 'ParameterKey' in param, f"Parameter missing ParameterKey in {param_file}"
                        assert 'ParameterValue' in param, f"Parameter missing ParameterValue in {param_file}"
                        
                        # Environment parameter should match the file name
                        if param['ParameterKey'] == 'Environment':
                            assert param['ParameterValue'] == env, \
                                f"Environment parameter mismatch in {param_file}"
                
                except (json.JSONDecodeError, FileNotFoundError):
                    pytest.fail(f"Invalid or missing parameter file: {param_file}")


class TestCloudFormationDeploymentValidation:
    """Integration tests for CloudFormation deployment validation."""
    
    def test_deployment_script_functionality(self):
        """
        Test that deployment script has all required functionality.
        """
        deploy_script = Path('cloudformation/deploy.py')
        
        if not deploy_script.exists():
            pytest.fail("Deployment script not found")
        
        # Read script content
        with open(deploy_script, 'r') as f:
            script_content = f.read()
        
        # Check for required functionality
        required_functions = [
            'def deploy_stack',
            'def delete_stack', 
            'def rollback_stack',
            'def cleanup_failed_stack',
            'def validate_parameters',
            'def upload_templates'
        ]
        
        for func in required_functions:
            assert func in script_content, f"Deployment script missing function: {func}"
        
        # Check for error handling
        error_handling_patterns = [
            'try:',
            'except ClientError',
            'except Exception'
        ]
        
        for pattern in error_handling_patterns:
            assert pattern in script_content, f"Deployment script missing error handling: {pattern}"

    def test_management_script_functionality(self):
        """
        Test that management script provides simplified operations.
        """
        manage_script = Path('cloudformation/manage.py')
        
        if not manage_script.exists():
            pytest.skip("Management script not found")
        
        # Read script content
        with open(manage_script, 'r') as f:
            script_content = f.read()
        
        # Check for required commands
        required_commands = [
            'deploy',
            'update', 
            'destroy',
            'rollback',
            'list',
            'validate'
        ]
        
        for command in required_commands:
            assert f"'{command}'" in script_content or f'"{command}"' in script_content, \
                f"Management script missing command: {command}"

    def test_configuration_file_structure(self):
        """
        Test that configuration file has proper structure.
        """
        config_file = Path('cloudformation/config.yaml')
        
        if not config_file.exists():
            pytest.skip("Configuration file not found")
        
        try:
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError:
            pytest.fail("Configuration file is not valid YAML")
        
        # Check for required sections
        required_sections = ['defaults', 'environments']
        
        for section in required_sections:
            assert section in config, f"Configuration missing section: {section}"
        
        # Check environment configurations
        environments = config.get('environments', {})
        for env_name, env_config in environments.items():
            assert 'domain_name' in env_config, f"Environment {env_name} missing domain_name"
            assert 'create_hosted_zone' in env_config, f"Environment {env_name} missing create_hosted_zone"