#!/usr/bin/env python3
"""
Management script for static website infrastructure operations.
Provides simplified commands for common deployment tasks.
"""

import argparse
import sys
import subprocess
import os
from pathlib import Path


def run_command(cmd: list, cwd: str = None) -> bool:
    """Run a command and return success status."""
    try:
        result = subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {' '.join(cmd)}")
        print(f"Error: {e.stderr}")
        return False


def deploy_infrastructure(environment: str, stack_name: str, template_bucket: str) -> bool:
    """Deploy the complete infrastructure."""
    print(f"Deploying infrastructure for {environment} environment...")
    
    # Change to cloudformation directory
    cf_dir = Path(__file__).parent
    
    # Upload templates first
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', stack_name,
        '--environment', environment,
        '--template-bucket', template_bucket,
        '--upload-templates',
        '--create-bucket'
    ]
    
    if not run_command(cmd, cwd=cf_dir):
        return False
    
    # Deploy the stack
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', stack_name,
        '--environment', environment,
        '--template-bucket', template_bucket
    ]
    
    return run_command(cmd, cwd=cf_dir)


def update_infrastructure(environment: str, stack_name: str, template_bucket: str) -> bool:
    """Update existing infrastructure."""
    print(f"Updating infrastructure for {environment} environment...")
    
    cf_dir = Path(__file__).parent
    
    # Upload updated templates
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', stack_name,
        '--environment', environment,
        '--template-bucket', template_bucket,
        '--upload-templates'
    ]
    
    if not run_command(cmd, cwd=cf_dir):
        return False
    
    # Update the stack
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', stack_name,
        '--environment', environment,
        '--template-bucket', template_bucket
    ]
    
    return run_command(cmd, cwd=cf_dir)


def destroy_infrastructure(environment: str, stack_name: str) -> bool:
    """Destroy the infrastructure."""
    print(f"Destroying infrastructure for {environment} environment...")
    
    # Confirm destruction
    response = input(f"Are you sure you want to delete stack '{stack_name}'? (yes/no): ")
    if response.lower() != 'yes':
        print("Destruction cancelled.")
        return True
    
    cf_dir = Path(__file__).parent
    
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', stack_name,
        '--environment', environment,
        '--delete'
    ]
    
    return run_command(cmd, cwd=cf_dir)


def rollback_infrastructure(environment: str, stack_name: str) -> bool:
    """Rollback failed infrastructure update."""
    print(f"Rolling back infrastructure for {environment} environment...")
    
    cf_dir = Path(__file__).parent
    
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', stack_name,
        '--environment', environment,
        '--rollback'
    ]
    
    return run_command(cmd, cwd=cf_dir)


def list_stacks() -> bool:
    """List all CloudFormation stacks."""
    cf_dir = Path(__file__).parent
    
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', 'dummy',  # Required but not used for list
        '--list'
    ]
    
    return run_command(cmd, cwd=cf_dir)


def validate_templates() -> bool:
    """Validate CloudFormation templates."""
    print("Validating CloudFormation templates...")
    
    cf_dir = Path(__file__).parent
    
    # Validate master template
    cmd = [
        'python3', 'deploy.py',
        '--stack-name', 'dummy',  # Required but not used for validation
        '--validate'
    ]
    
    return run_command(cmd, cwd=cf_dir)


def main():
    """Main management function."""
    parser = argparse.ArgumentParser(description='Manage static website infrastructure')
    parser.add_argument('--environment', '-e', choices=['dev', 'staging', 'prod'],
                       default='prod', help='Environment to manage')
    parser.add_argument('--stack-name', '-s', help='CloudFormation stack name')
    parser.add_argument('--template-bucket', '-b', help='S3 bucket for templates')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Deploy command
    deploy_parser = subparsers.add_parser('deploy', help='Deploy infrastructure')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update infrastructure')
    
    # Destroy command
    destroy_parser = subparsers.add_parser('destroy', help='Destroy infrastructure')
    
    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback failed update')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List stacks')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate templates')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Generate default stack name if not provided
    if not args.stack_name and args.command not in ['list', 'validate']:
        args.stack_name = f"static-website-{args.environment}"
    
    # Generate default template bucket if not provided
    if not args.template_bucket and args.command not in ['list', 'validate', 'destroy', 'rollback']:
        args.template_bucket = f"cloudformation-templates-{args.environment}-{hash(os.getcwd()) % 10000:04d}"
    
    # Execute command
    success = False
    
    if args.command == 'deploy':
        success = deploy_infrastructure(args.environment, args.stack_name, args.template_bucket)
    elif args.command == 'update':
        success = update_infrastructure(args.environment, args.stack_name, args.template_bucket)
    elif args.command == 'destroy':
        success = destroy_infrastructure(args.environment, args.stack_name)
    elif args.command == 'rollback':
        success = rollback_infrastructure(args.environment, args.stack_name)
    elif args.command == 'list':
        success = list_stacks()
    elif args.command == 'validate':
        success = validate_templates()
    
    if success:
        print(f"\n✅ Command '{args.command}' completed successfully!")
    else:
        print(f"\n❌ Command '{args.command}' failed!")
        sys.exit(1)


if __name__ == '__main__':
    main()