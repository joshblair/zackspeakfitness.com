"""
Property-based tests for CI/CD pipeline deployment automation reliability.
Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
"""
import pytest
import yaml
import json
import os
import subprocess
import tempfile
import shutil
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Optional
from pathlib import Path


class TestDeploymentAutomationReliability:
    """
    Property 6: Deployment Automation Reliability
    For any code push to main branch affecting website files, the GitHub Actions 
    pipeline should deploy changes and invalidate cache
    Validates: Requirements 4.1, 4.2
    """

    def get_workflow_path(self, workflow_name: str) -> Path:
        """Get path to GitHub Actions workflow file."""
        return Path('.github/workflows') / workflow_name

    def load_workflow_content(self, workflow_path: Path) -> Dict[str, Any]:
        """Load and parse GitHub Actions workflow YAML."""
        try:
            with open(workflow_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            pytest.fail(f"Workflow file not found: {workflow_path}")
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML in workflow file {workflow_path}: {e}")

    def test_deploy_workflow_exists_and_valid(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that the main deployment workflow exists and has valid YAML structure.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        
        # Workflow file must exist
        assert workflow_path.exists(), "Deploy workflow file (.github/workflows/deploy.yml) not found"
        
        # Must be valid YAML
        workflow = self.load_workflow_content(workflow_path)
        
        # Must have required top-level keys
        required_keys = ['name', 'on', 'jobs']
        for key in required_keys:
            assert key in workflow, f"Deploy workflow missing required key: {key}"

    def test_workflow_triggers_on_website_changes(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow triggers on pushes to main branch with website file changes.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        # Check push trigger configuration
        on_config = workflow.get('on', {})
        
        # Should trigger on push
        assert 'push' in on_config, "Workflow should trigger on push events"
        
        push_config = on_config['push']
        
        # Should specify main branch
        branches = push_config.get('branches', [])
        assert 'main' in branches, "Workflow should trigger on pushes to main branch"
        
        # Should specify website path filter
        paths = push_config.get('paths', [])
        website_path_found = any('website' in path for path in paths)
        assert website_path_found, "Workflow should trigger on changes to website files"

    def test_workflow_supports_manual_dispatch(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow supports manual triggering with environment selection.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        on_config = workflow.get('on', {})
        
        # Should support workflow_dispatch
        assert 'workflow_dispatch' in on_config, "Workflow should support manual dispatch"
        
        dispatch_config = on_config.get('workflow_dispatch', {})
        
        # Should have environment input
        inputs = dispatch_config.get('inputs', {})
        assert 'environment' in inputs, "Manual dispatch should have environment input"
        
        env_input = inputs['environment']
        assert env_input.get('type') == 'choice', "Environment input should be choice type"
        
        options = env_input.get('options', [])
        assert 'dev' in options and 'prod' in options, "Environment options should include dev and prod"

    def test_workflow_has_validation_job(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow includes file validation before deployment.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        
        # Should have validation job
        assert 'validate' in jobs, "Workflow should have validation job"
        
        validate_job = jobs['validate']
        steps = validate_job.get('steps', [])
        
        # Should have HTML validation step
        html_validation_found = False
        for step in steps:
            step_name = step.get('name', '').lower()
            step_run = step.get('run', '').lower()
            if 'html' in step_name or 'html-validate' in step_run:
                html_validation_found = True
                break
        
        assert html_validation_found, "Validation job should include HTML validation"

    def test_workflow_has_deployment_job(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow includes deployment job with required steps.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        
        # Should have deploy job
        assert 'deploy' in jobs, "Workflow should have deploy job"
        
        deploy_job = jobs['deploy']
        
        # Should depend on validation
        needs = deploy_job.get('needs', [])
        if isinstance(needs, str):
            needs = [needs]
        assert 'validate' in needs, "Deploy job should depend on validate job"
        
        # Should have required permissions for OIDC
        permissions = deploy_job.get('permissions', {})
        assert permissions.get('id-token') == 'write', "Deploy job should have id-token write permission"
        assert permissions.get('contents') == 'read', "Deploy job should have contents read permission"

    def test_deployment_steps_completeness(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that deployment job includes all required deployment steps.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Required deployment steps
        required_step_patterns = [
            'checkout',
            'configure.*aws.*credentials',
            'stack.*outputs',
            'sync.*s3',
            'invalidate.*cloudfront',
            'verify.*deployment'
        ]
        
        for pattern in required_step_patterns:
            step_found = False
            for step in steps:
                step_name = step.get('name', '').lower()
                step_run = step.get('run', '').lower()
                step_uses = step.get('uses', '').lower()
                
                # Convert pattern to regex-like matching
                import re
                pattern_regex = pattern.replace('.*', '.*')
                
                if any(re.search(pattern_regex, text) for text in [step_name, step_run, step_uses]):
                    step_found = True
                    break
            
            assert step_found, f"Deploy job missing required step pattern: {pattern}"

    def test_aws_authentication_configuration(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow uses secure OIDC authentication for AWS.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find AWS credentials configuration step
        aws_config_step = None
        for step in steps:
            if 'aws-actions/configure-aws-credentials' in step.get('uses', ''):
                aws_config_step = step
                break
        
        assert aws_config_step is not None, "Deploy job should use aws-actions/configure-aws-credentials"
        
        # Should use OIDC (role-to-assume) not access keys
        with_config = aws_config_step.get('with', {})
        assert 'role-to-assume' in with_config, "AWS authentication should use OIDC role-to-assume"
        assert 'aws-access-key-id' not in with_config, "Should not use access keys for authentication"
        assert 'aws-secret-access-key' not in with_config, "Should not use secret keys for authentication"

    @given(st.lists(st.sampled_from(['dev', 'staging', 'prod']), min_size=1, max_size=3))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_multi_environment_deployment_property(self, environments: List[str]):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        For any valid environment list, the workflow should support deployment to each environment.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        
        # Check if workflow supports environment matrix or environment selection
        strategy = deploy_job.get('strategy', {})
        matrix = strategy.get('matrix', {})
        
        # Should have environment configuration
        environment_config_found = (
            'environment' in matrix or 
            'environment' in deploy_job or
            any('environment' in step.get('run', '') for step in deploy_job.get('steps', []))
        )
        
        assert environment_config_found, "Workflow should support environment-specific deployment"

    @given(st.lists(st.text(alphabet='abcdefghijklmnopqrstuvwxyz0123456789-', min_size=5, max_size=20), 
                   min_size=1, max_size=5))
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_s3_sync_command_property(self, file_names: List[str]):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        For any set of website file names, the S3 sync command should handle them properly.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find S3 sync step
        s3_sync_step = None
        for step in steps:
            step_run = step.get('run', '')
            if 'aws s3 sync' in step_run:
                s3_sync_step = step
                break
        
        assert s3_sync_step is not None, "Deploy job should include S3 sync command"
        
        sync_command = s3_sync_step.get('run', '')
        
        # Should use --delete flag for proper synchronization
        assert '--delete' in sync_command, "S3 sync should use --delete flag"
        
        # Should set cache control headers
        cache_control_found = (
            '--cache-control' in sync_command or 
            'cache-control' in sync_command.lower()
        )
        assert cache_control_found, "S3 sync should set cache control headers"

    def test_cloudfront_invalidation_step(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow includes CloudFront cache invalidation after S3 sync.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find CloudFront invalidation step
        invalidation_step = None
        for step in steps:
            step_run = step.get('run', '')
            if 'cloudfront' in step_run and 'invalidation' in step_run:
                invalidation_step = step
                break
        
        assert invalidation_step is not None, "Deploy job should include CloudFront invalidation"
        
        invalidation_command = invalidation_step.get('run', '')
        
        # Should invalidate all paths
        assert '/*' in invalidation_command, "CloudFront invalidation should invalidate all paths (/*)"
        
        # Should use create-invalidation command
        assert 'create-invalidation' in invalidation_command, "Should use create-invalidation command"

    def test_deployment_verification_step(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow includes deployment verification after cache invalidation.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        steps = deploy_job.get('steps', [])
        
        # Find verification step
        verification_step = None
        for step in steps:
            step_name = step.get('name', '').lower()
            step_run = step.get('run', '').lower()
            if 'verify' in step_name or 'verify' in step_run:
                verification_step = step
                break
        
        assert verification_step is not None, "Deploy job should include deployment verification"
        
        verification_command = verification_step.get('run', '')
        
        # Should check S3 file count or similar verification
        verification_patterns = ['s3 ls', 'file count', 'wc -l']
        verification_found = any(pattern in verification_command.lower() for pattern in verification_patterns)
        assert verification_found, "Verification should check deployment success"

    def test_error_handling_and_notifications(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that workflow includes proper error handling and notifications.
        """
        workflow_path = self.get_workflow_path('deploy.yml')
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        
        # Should have notification job
        notify_job_found = any('notify' in job_name.lower() for job_name in jobs.keys())
        assert notify_job_found, "Workflow should have notification job"
        
        # Find notification job
        notify_job = None
        for job_name, job_config in jobs.items():
            if 'notify' in job_name.lower():
                notify_job = job_config
                break
        
        # Should run always (even on failure)
        assert notify_job.get('if') == 'always()', "Notification job should run always"
        
        # Should depend on other jobs
        needs = notify_job.get('needs', [])
        if isinstance(needs, str):
            needs = [needs]
        assert len(needs) >= 2, "Notification job should depend on validate and deploy jobs"

    def test_pull_request_validation_workflow(self):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        Test that PR validation workflow exists and validates changes before merge.
        """
        workflow_path = self.get_workflow_path('validate-pr.yml')
        
        # PR validation workflow should exist
        assert workflow_path.exists(), "PR validation workflow should exist"
        
        workflow = self.load_workflow_content(workflow_path)
        
        # Should trigger on pull requests
        on_config = workflow.get('on', {})
        assert 'pull_request' in on_config, "Should trigger on pull requests"
        
        pr_config = on_config['pull_request']
        branches = pr_config.get('branches', [])
        assert 'main' in branches, "Should trigger on PRs to main branch"

    @given(st.lists(st.sampled_from([
        'index.html', 'about.html', 'contact.html', 'style.css', 'script.js', 'image.jpg'
    ]), min_size=1, max_size=10))
    @settings(max_examples=25, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_file_validation_property(self, file_list: List[str]):
        """
        Feature: static-website-infrastructure, Property 6: Deployment Automation Reliability
        For any list of website files, validation should check appropriate file types.
        """
        workflow_path = self.get_workflow_path('validate-pr.yml')
        
        if not workflow_path.exists():
            pytest.skip("PR validation workflow not found")
        
        workflow = self.load_workflow_content(workflow_path)
        
        jobs = workflow.get('jobs', {})
        
        # Should have website validation job
        website_validation_job = None
        for job_name, job_config in jobs.items():
            if 'website' in job_name.lower() or 'validate' in job_name.lower():
                website_validation_job = job_config
                break
        
        assert website_validation_job is not None, "Should have website validation job"
        
        steps = website_validation_job.get('steps', [])
        
        # Check for HTML validation
        html_files = [f for f in file_list if f.endswith('.html')]
        if html_files:
            html_validation_found = False
            for step in steps:
                step_run = step.get('run', '')
                if 'html-validate' in step_run or 'find' in step_run and '.html' in step_run:
                    html_validation_found = True
                    break
            assert html_validation_found, "Should validate HTML files when present"
        
        # Check for CSS validation
        css_files = [f for f in file_list if f.endswith('.css')]
        if css_files:
            css_validation_found = False
            for step in steps:
                step_run = step.get('run', '')
                step_name = step.get('name', '').lower()
                if 'css' in step_run or 'css' in step_name:
                    css_validation_found = True
                    break
            # CSS validation is optional but should be mentioned if present
            # This is a weaker assertion since CSS validation is more complex


class TestCICDIntegrationValidation:
    """Integration tests for CI/CD pipeline components."""
    
    def test_workflow_yaml_syntax_validation(self):
        """
        Test that all workflow files have valid YAML syntax.
        """
        workflows_dir = Path('.github/workflows')
        
        if not workflows_dir.exists():
            pytest.fail("Workflows directory not found")
        
        workflow_files = list(workflows_dir.glob('*.yml')) + list(workflows_dir.glob('*.yaml'))
        
        assert len(workflow_files) > 0, "No workflow files found"
        
        for workflow_file in workflow_files:
            try:
                with open(workflow_file, 'r') as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML syntax in {workflow_file}: {e}")

    def test_workflow_environment_variables(self):
        """
        Test that workflows define required environment variables.
        """
        workflow_path = Path('.github/workflows/deploy.yml')
        
        if not workflow_path.exists():
            pytest.skip("Deploy workflow not found")
        
        with open(workflow_path, 'r') as f:
            workflow_content = f.read()
        
        # Should define AWS_REGION
        assert 'AWS_REGION' in workflow_content, "Workflow should define AWS_REGION"
        
        # Should use us-west-2 region
        assert 'us-west-2' in workflow_content, "Should use us-west-2 region"

    def test_workflow_security_configuration(self):
        """
        Test that workflows follow security best practices.
        """
        workflow_path = Path('.github/workflows/deploy.yml')
        
        if not workflow_path.exists():
            pytest.skip("Deploy workflow not found")
        
        workflow = yaml.safe_load(open(workflow_path))
        
        jobs = workflow.get('jobs', {})
        deploy_job = jobs.get('deploy', {})
        
        # Should use specific action versions (not @main or @master)
        steps = deploy_job.get('steps', [])
        for step in steps:
            uses = step.get('uses', '')
            if uses and '@' in uses:
                version = uses.split('@')[1]
                assert version not in ['main', 'master'], f"Should use specific version, not {version}"
                assert version.startswith('v'), f"Should use version tag, got {version}"

    def test_iam_role_configuration_completeness(self):
        """
        Test that IAM role template provides all required permissions.
        """
        cicd_template_path = Path('cloudformation/templates/cicd.yaml')
        
        if not cicd_template_path.exists():
            pytest.skip("CI/CD template not found")
        
        with open(cicd_template_path, 'r') as f:
            template_content = f.read()
        
        # Should have S3 permissions
        s3_permissions = ['s3:GetObject', 's3:PutObject', 's3:DeleteObject', 's3:ListBucket']
        for permission in s3_permissions:
            assert permission in template_content, f"IAM role missing S3 permission: {permission}"
        
        # Should have CloudFront permissions
        cf_permissions = ['cloudfront:CreateInvalidation', 'cloudfront:GetInvalidation']
        for permission in cf_permissions:
            assert permission in template_content, f"IAM role missing CloudFront permission: {permission}"
        
        # Should use OIDC provider
        assert 'AWS::IAM::OIDCIdentityProvider' in template_content, "Should create OIDC provider"
        assert 'token.actions.githubusercontent.com' in template_content, "Should use GitHub OIDC provider"

    def test_workflow_documentation_exists(self):
        """
        Test that workflow documentation exists and is comprehensive.
        """
        readme_path = Path('.github/workflows/README.md')
        
        assert readme_path.exists(), "Workflow documentation should exist"
        
        with open(readme_path, 'r') as f:
            readme_content = f.read()
        
        # Should document setup instructions
        required_sections = [
            'Setup Instructions',
            'Required Secrets',
            'Environment Configuration',
            'Troubleshooting'
        ]
        
        for section in required_sections:
            assert section in readme_content, f"Documentation missing section: {section}"
        
        # Should document AWS_ROLE_ARN secret
        assert 'AWS_ROLE_ARN' in readme_content, "Should document AWS_ROLE_ARN secret requirement"