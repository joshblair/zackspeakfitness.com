#!/usr/bin/env python3
"""
CloudFormation deployment script for static website infrastructure.
Handles nested stack deployment with proper dependency management.
"""

import argparse
import json
import sys
import time
import os
from typing import Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import yaml


class CloudFormationDeployer:
    """Handles CloudFormation stack deployment and management."""
    
    def __init__(self, region: str = 'us-west-2'):
        """Initialize the deployer with AWS clients."""
        try:
            self.cf_client = boto3.client('cloudformation', region_name=region)
            self.s3_client = boto3.client('s3', region_name=region)
            self.region = region
        except NoCredentialsError:
            print("Error: AWS credentials not configured. Please run 'aws configure' or set environment variables.")
            sys.exit(1)
    
    def load_config(self, config_file: str = 'config.yaml') -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"Configuration file not found: {config_file}")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing configuration file: {e}")
            return {}
    
    def validate_parameters(self, parameters: List[Dict]) -> bool:
        """Validate required parameters are present."""
        required_params = ['DomainName', 'Environment', 'TemplateS3Bucket']
        param_keys = [p['ParameterKey'] for p in parameters]
        
        missing_params = [p for p in required_params if p not in param_keys]
        if missing_params:
            print(f"Missing required parameters: {missing_params}")
            return False
        
        # Validate domain name format
        domain_param = next((p for p in parameters if p['ParameterKey'] == 'DomainName'), None)
        if domain_param:
            domain = domain_param['ParameterValue']
            if not self._is_valid_domain(domain):
                print(f"Invalid domain name format: {domain}")
                return False
        
        return True
    
    def _is_valid_domain(self, domain: str) -> bool:
        """Validate domain name format."""
        import re
        pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$'
        return re.match(pattern, domain) is not None
    
    def create_template_bucket(self, bucket_name: str) -> bool:
        """Create S3 bucket for CloudFormation templates if it doesn't exist."""
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=bucket_name)
            print(f"Template bucket {bucket_name} already exists")
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                # Bucket doesn't exist, create it
                try:
                    if self.region == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': self.region}
                        )
                    
                    # Enable versioning
                    self.s3_client.put_bucket_versioning(
                        Bucket=bucket_name,
                        VersioningConfiguration={'Status': 'Enabled'}
                    )
                    
                    print(f"Created template bucket: {bucket_name}")
                    return True
                    
                except ClientError as create_error:
                    print(f"Error creating bucket: {create_error}")
                    return False
            else:
                print(f"Error checking bucket: {e}")
                return False
    
    def upload_templates(self, bucket_name: str, local_path: str = 'templates/') -> bool:
        """Upload nested templates to S3 bucket."""
        try:
            templates = [
                'certificate.yaml',
                'storage.yaml', 
                'distribution.yaml',
                'dns.yaml',
                'cicd.yaml'
            ]
            
            for template in templates:
                local_file = f"{local_path}{template}"
                s3_key = f"templates/{template}"
                
                print(f"Uploading {local_file} to s3://{bucket_name}/{s3_key}")
                self.s3_client.upload_file(local_file, bucket_name, s3_key)
                
            return True
            
        except ClientError as e:
            print(f"Error uploading templates: {e}")
            return False
        except FileNotFoundError as e:
            print(f"Template file not found: {e}")
            return False
    
    def load_parameters(self, parameter_file: str) -> List[Dict]:
        """Load parameters from JSON file."""
        try:
            with open(parameter_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Parameter file not found: {parameter_file}")
            return []
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in parameter file: {e}")
            return []
    
    def deploy_stack(self, stack_name: str, template_file: str, 
                    parameters: List[Dict], capabilities: List[str] = None) -> bool:
        """Deploy or update a CloudFormation stack."""
        try:
            with open(template_file, 'r') as f:
                template_body = f.read()
            
            # Check if stack exists
            stack_exists = self._stack_exists(stack_name)
            
            if capabilities is None:
                capabilities = ['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM']
            
            if stack_exists:
                print(f"Updating existing stack: {stack_name}")
                response = self.cf_client.update_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=capabilities,
                    Tags=[
                        {'Key': 'Project', 'Value': 'StaticWebsite'},
                        {'Key': 'ManagedBy', 'Value': 'CloudFormation'}
                    ]
                )
                operation = 'UPDATE'
            else:
                print(f"Creating new stack: {stack_name}")
                response = self.cf_client.create_stack(
                    StackName=stack_name,
                    TemplateBody=template_body,
                    Parameters=parameters,
                    Capabilities=capabilities,
                    OnFailure='ROLLBACK',
                    Tags=[
                        {'Key': 'Project', 'Value': 'StaticWebsite'},
                        {'Key': 'ManagedBy', 'Value': 'CloudFormation'}
                    ]
                )
                operation = 'CREATE'
            
            # Wait for completion
            return self._wait_for_completion(stack_name, operation)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ValidationError' and 'No updates are to be performed' in str(e):
                print(f"No changes detected for stack {stack_name}")
                return True
            else:
                print(f"Error deploying stack {stack_name}: {e}")
                return False
        except FileNotFoundError:
            print(f"Template file not found: {template_file}")
            return False
    
    def _stack_exists(self, stack_name: str) -> bool:
        """Check if a CloudFormation stack exists."""
        try:
            self.cf_client.describe_stacks(StackName=stack_name)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                return False
            raise
    
    def _wait_for_completion(self, stack_name: str, operation: str) -> bool:
        """Wait for stack operation to complete."""
        if operation == 'CREATE':
            waiter = self.cf_client.get_waiter('stack_create_complete')
            success_status = 'CREATE_COMPLETE'
            failure_statuses = ['CREATE_FAILED', 'ROLLBACK_COMPLETE', 'ROLLBACK_FAILED']
        else:  # UPDATE
            waiter = self.cf_client.get_waiter('stack_update_complete')
            success_status = 'UPDATE_COMPLETE'
            failure_statuses = ['UPDATE_FAILED', 'UPDATE_ROLLBACK_COMPLETE', 'UPDATE_ROLLBACK_FAILED']
        
        print(f"Waiting for {operation.lower()} to complete...")
        
        try:
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 120  # 60 minutes max
                }
            )
            print(f"Stack {operation.lower()} completed successfully!")
            return True
            
        except Exception as e:
            # Check final status
            try:
                response = self.cf_client.describe_stacks(StackName=stack_name)
                status = response['Stacks'][0]['StackStatus']
                
                if status in failure_statuses:
                    print(f"Stack {operation.lower()} failed with status: {status}")
                    self._print_stack_events(stack_name)
                    return False
                elif status == success_status:
                    print(f"Stack {operation.lower()} completed successfully!")
                    return True
                else:
                    print(f"Stack in unexpected status: {status}")
                    return False
                    
            except ClientError:
                print(f"Error checking stack status: {e}")
                return False
    
    def _print_stack_events(self, stack_name: str, limit: int = 10):
        """Print recent stack events for debugging."""
        try:
            response = self.cf_client.describe_stack_events(StackName=stack_name)
            events = response['StackEvents'][:limit]
            
            print(f"\nRecent stack events for {stack_name}:")
            print("-" * 80)
            
            for event in events:
                timestamp = event['Timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                resource_type = event.get('ResourceType', 'N/A')
                logical_id = event.get('LogicalResourceId', 'N/A')
                status = event.get('ResourceStatus', 'N/A')
                reason = event.get('ResourceStatusReason', 'N/A')
                
                print(f"{timestamp} | {resource_type} | {logical_id}")
                print(f"  Status: {status}")
                if reason != 'N/A':
                    print(f"  Reason: {reason}")
                print()
                
        except ClientError as e:
            print(f"Error retrieving stack events: {e}")
    
    def get_stack_outputs(self, stack_name: str) -> Dict[str, str]:
        """Get stack outputs as a dictionary."""
        try:
            response = self.cf_client.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            
            outputs = {}
            if 'Outputs' in stack:
                for output in stack['Outputs']:
                    outputs[output['OutputKey']] = output['OutputValue']
            
            return outputs
            
        except ClientError as e:
            print(f"Error getting stack outputs: {e}")
            return {}
    
    def rollback_stack(self, stack_name: str) -> bool:
        """Rollback a failed stack update."""
        try:
            print(f"Rolling back stack: {stack_name}")
            
            # Check if stack is in a rollback-able state
            response = self.cf_client.describe_stacks(StackName=stack_name)
            stack_status = response['Stacks'][0]['StackStatus']
            
            rollback_states = [
                'UPDATE_ROLLBACK_FAILED',
                'UPDATE_FAILED'
            ]
            
            if stack_status not in rollback_states:
                print(f"Stack is in {stack_status} state, cannot rollback")
                return False
            
            # Continue rollback
            self.cf_client.continue_update_rollback(StackName=stack_name)
            
            # Wait for rollback completion
            waiter = self.cf_client.get_waiter('stack_update_rollback_complete')
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 120
                }
            )
            
            print(f"Stack rollback completed successfully!")
            return True
            
        except ClientError as e:
            print(f"Error rolling back stack: {e}")
            return False
    
    def cleanup_failed_stack(self, stack_name: str) -> bool:
        """Clean up a failed stack creation."""
        try:
            response = self.cf_client.describe_stacks(StackName=stack_name)
            stack_status = response['Stacks'][0]['StackStatus']
            
            cleanup_states = [
                'CREATE_FAILED',
                'ROLLBACK_COMPLETE',
                'ROLLBACK_FAILED'
            ]
            
            if stack_status in cleanup_states:
                print(f"Cleaning up failed stack: {stack_name}")
                return self.delete_stack(stack_name)
            else:
                print(f"Stack is in {stack_status} state, no cleanup needed")
                return True
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                print(f"Stack {stack_name} does not exist")
                return True
            print(f"Error checking stack status: {e}")
            return False
    
    def list_stacks(self, status_filter: List[str] = None) -> List[Dict]:
        """List CloudFormation stacks with optional status filter."""
        try:
            if status_filter is None:
                status_filter = [
                    'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'CREATE_IN_PROGRESS',
                    'UPDATE_IN_PROGRESS', 'CREATE_FAILED', 'UPDATE_FAILED'
                ]
            
            response = self.cf_client.list_stacks(StackStatusFilter=status_filter)
            return response['StackSummaries']
            
        except ClientError as e:
            print(f"Error listing stacks: {e}")
            return []
    
    def get_stack_resources(self, stack_name: str) -> List[Dict]:
        """Get all resources in a stack."""
        try:
            response = self.cf_client.list_stack_resources(StackName=stack_name)
            return response['StackResourceSummaries']
            
        except ClientError as e:
            print(f"Error getting stack resources: {e}")
            return []
    
    def validate_template_file(self, template_file: str) -> Tuple[bool, str]:
        """Validate CloudFormation template file."""
        try:
            with open(template_file, 'r') as f:
                template_body = f.read()
            
            # Check for required CloudFormation sections
            required_sections = ['AWSTemplateFormatVersion', 'Resources']
            for section in required_sections:
                if section not in template_body:
                    return False, f"Missing required section: {section}"
            
            # Check for valid AWSTemplateFormatVersion
            if "'2010-09-09'" not in template_body and '"2010-09-09"' not in template_body:
                return False, "Invalid or missing AWSTemplateFormatVersion"
            
            # Basic YAML structure check - ensure it's not completely malformed
            try:
                # Count opening and closing braces/brackets for basic structure
                open_braces = template_body.count('{')
                close_braces = template_body.count('}')
                open_brackets = template_body.count('[')
                close_brackets = template_body.count(']')
                
                # For YAML, these should be balanced if present
                if open_braces != close_braces:
                    return False, "Unbalanced braces in template"
                if open_brackets != close_brackets:
                    return False, "Unbalanced brackets in template"
                    
            except Exception:
                pass  # Skip detailed validation if there are issues
            
            return True, "Template structure is valid"
            
        except FileNotFoundError:
            return False, f"Template file not found: {template_file}"
        except Exception as e:
            return False, f"Error validating template: {e}"
    
    def delete_stack(self, stack_name: str) -> bool:
        """Delete a CloudFormation stack."""
        try:
            print(f"Deleting stack: {stack_name}")
            self.cf_client.delete_stack(StackName=stack_name)
            
            waiter = self.cf_client.get_waiter('stack_delete_complete')
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 120
                }
            )
            
            print(f"Stack {stack_name} deleted successfully!")
            return True
            
        except ClientError as e:
            print(f"Error deleting stack: {e}")
            return False
        """Delete a CloudFormation stack."""
        try:
            print(f"Deleting stack: {stack_name}")
            self.cf_client.delete_stack(StackName=stack_name)
            
            waiter = self.cf_client.get_waiter('stack_delete_complete')
            waiter.wait(
                StackName=stack_name,
                WaiterConfig={
                    'Delay': 30,
                    'MaxAttempts': 120
                }
            )
            
            print(f"Stack {stack_name} deleted successfully!")
            return True
            
        except ClientError as e:
            print(f"Error deleting stack: {e}")
            return False


def main():
    """Main deployment function."""
    parser = argparse.ArgumentParser(description='Deploy static website infrastructure')
    parser.add_argument('--stack-name', required=True, help='CloudFormation stack name')
    parser.add_argument('--environment', choices=['dev', 'staging', 'prod'], 
                       default='prod', help='Environment to deploy')
    parser.add_argument('--template-bucket', help='S3 bucket for nested templates')
    parser.add_argument('--region', default='us-west-2', help='AWS region')
    parser.add_argument('--config', default='config.yaml', help='Configuration file')
    
    # Actions
    parser.add_argument('--delete', action='store_true', help='Delete the stack')
    parser.add_argument('--rollback', action='store_true', help='Rollback failed stack update')
    parser.add_argument('--cleanup', action='store_true', help='Clean up failed stack')
    parser.add_argument('--list', action='store_true', help='List stacks')
    parser.add_argument('--validate', action='store_true', help='Validate template only')
    parser.add_argument('--upload-templates', action='store_true', 
                       help='Upload nested templates to S3')
    parser.add_argument('--create-bucket', action='store_true',
                       help='Create template S3 bucket if it does not exist')
    
    args = parser.parse_args()
    
    deployer = CloudFormationDeployer(region=args.region)
    
    # Load configuration
    config = deployer.load_config(args.config)
    
    # Handle list action
    if args.list:
        stacks = deployer.list_stacks()
        if stacks:
            print("\nCloudFormation Stacks:")
            print("-" * 80)
            for stack in stacks:
                print(f"Name: {stack['StackName']}")
                print(f"Status: {stack['StackStatus']}")
                print(f"Created: {stack['CreationTime']}")
                if 'LastUpdatedTime' in stack:
                    print(f"Updated: {stack['LastUpdatedTime']}")
                print("-" * 40)
        else:
            print("No stacks found")
        return
    
    # Handle validation action
    if args.validate:
        is_valid, message = deployer.validate_template_file('master-template.yaml')
        print(f"Template validation: {message}")
        sys.exit(0 if is_valid else 1)
    
    # Handle rollback action
    if args.rollback:
        success = deployer.rollback_stack(args.stack_name)
        sys.exit(0 if success else 1)
    
    # Handle cleanup action
    if args.cleanup:
        success = deployer.cleanup_failed_stack(args.stack_name)
        sys.exit(0 if success else 1)
    
    # Handle delete action
    if args.delete:
        success = deployer.delete_stack(args.stack_name)
        sys.exit(0 if success else 1)
    
    # Determine template bucket
    template_bucket = args.template_bucket
    if not template_bucket and config:
        env_config = config.get('environments', {}).get(args.environment, {})
        template_bucket = env_config.get('template_bucket')
    
    if not template_bucket:
        print("Error: Template bucket not specified. Use --template-bucket or configure in config.yaml")
        sys.exit(1)
    
    # Create bucket if requested
    if args.create_bucket:
        success = deployer.create_template_bucket(template_bucket)
        if not success:
            sys.exit(1)
    
    # Upload templates if requested
    if args.upload_templates:
        print("Uploading nested templates...")
        success = deployer.upload_templates(template_bucket)
        if not success:
            sys.exit(1)
    
    # Load parameters
    parameter_file = f"parameters/{args.environment}.json"
    parameters = deployer.load_parameters(parameter_file)
    
    if not parameters:
        print(f"Failed to load parameters from {parameter_file}")
        sys.exit(1)
    
    # Add template bucket parameter
    parameters.append({
        'ParameterKey': 'TemplateS3Bucket',
        'ParameterValue': template_bucket
    })
    
    # Validate parameters
    if not deployer.validate_parameters(parameters):
        sys.exit(1)
    
    # Validate template
    is_valid, message = deployer.validate_template_file('master-template.yaml')
    if not is_valid:
        print(f"Template validation failed: {message}")
        sys.exit(1)
    
    # Deploy master stack
    success = deployer.deploy_stack(
        stack_name=args.stack_name,
        template_file='master-template.yaml',
        parameters=parameters
    )
    
    if success:
        print("\nDeployment completed successfully!")
        
        # Print important outputs
        outputs = deployer.get_stack_outputs(args.stack_name)
        if outputs:
            print("\nStack Outputs:")
            print("-" * 40)
            for key, value in outputs.items():
                print(f"{key}: {value}")
    else:
        print("\nDeployment failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()