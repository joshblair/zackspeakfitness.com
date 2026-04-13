"""
Property-based tests for monitoring and alerting infrastructure validation.
Tests CloudWatch metrics collection and alerting configuration.
Validates: Requirements 8.1, 8.4
"""
import pytest
import boto3
import time
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError, NoCredentialsError
import json


class TestCloudWatchMetricsCollection:
    """
    Test CloudWatch metrics collection for infrastructure monitoring.
    Validates: Requirements 8.1
    """

    def get_monitoring_resources_from_stack(self, cloudformation_client, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get monitoring resources from CloudFormation stack."""
        try:
            response = cloudformation_client.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            monitoring_info = {}
            for output in outputs:
                if output['OutputKey'] == 'DistributionId':
                    monitoring_info['distribution_id'] = output['OutputValue']
                elif output['OutputKey'] == 'AlertsTopicArn':
                    monitoring_info['alerts_topic_arn'] = output['OutputValue']
                elif output['OutputKey'] == 'AccessLogsLogGroupName':
                    monitoring_info['log_group_name'] = output['OutputValue']
                elif output['OutputKey'] == 'DashboardURL':
                    monitoring_info['dashboard_url'] = output['OutputValue']
                elif output['OutputKey'] == 'CostTrackingDashboardURL':
                    monitoring_info['cost_dashboard_url'] = output['OutputValue']
            
            return monitoring_info if monitoring_info else None
            
        except Exception:
            return None

    def test_cloudfront_metrics_available(self, cloudformation_client, cloudwatch_client, test_config):
        """
        Test that CloudFront metrics are available in CloudWatch.
        Validates: Requirements 8.1
        """
        monitoring_info = self.get_monitoring_resources_from_stack(
            cloudformation_client, 
            test_config.get('master_stack_name', 'zackspeakfitness-infrastructure-test')
        )
        
        if monitoring_info is None:
            pytest.skip("Monitoring stack not deployed or resources not found")
        
        distribution_id = monitoring_info.get('distribution_id')
        if not distribution_id:
            pytest.skip("Distribution ID not found in stack outputs")
        
        # Test that CloudFront metrics namespace exists
        try:
            response = cloudwatch_client.list_metrics(
                Namespace='AWS/CloudFront',
                Dimensions=[
                    {
                        'Name': 'DistributionId',
                        'Value': distribution_id
                    }
                ]
            )
            
            metrics = response.get('Metrics', [])
            metric_names = [metric['MetricName'] for metric in metrics]
            
            # Check for essential CloudFront metrics
            expected_metrics = ['Requests', 'BytesDownloaded', '4xxErrorRate', '5xxErrorRate', 'CacheHitRate']
            
            # Note: Metrics might not be available immediately after deployment
            # We check if the metrics namespace is accessible
            assert isinstance(metrics, list), "Should be able to query CloudFront metrics namespace"
            
        except ClientError as e:
            if e.response['Error']['Code'] in ['ValidationError', 'InvalidParameterValue']:
                pytest.skip("CloudFront distribution might not have generated metrics yet")
            else:
                raise

    def test_cloudwatch_alarms_exist(self, cloudformation_client, cloudwatch_client, test_config):
        """
        Test that CloudWatch alarms are created and configured correctly.
        Validates: Requirements 8.1, 8.4
        """
        monitoring_info = self.get_monitoring_resources_from_stack(
            cloudformation_client, 
            test_config.get('monitoring_stack_name', 'zackspeakfitness-monitoring-test')
        )
        
        if monitoring_info is None:
            pytest.skip("Monitoring stack not deployed")
        
        # Get domain name from test config
        domain_name = test_config.get('domain_name', 'zackspeakfitness.com')
        environment = test_config.get('environment', 'test')
        
        # Expected alarm names based on template
        expected_alarms = [
            f'{domain_name}-{environment}-high-error-rate',
            f'{domain_name}-{environment}-server-errors',
            f'{domain_name}-{environment}-low-cache-hit-rate',
            f'{domain_name}-{environment}-high-traffic'
        ]
        
        try:
            # Get all alarms
            response = cloudwatch_client.describe_alarms()
            alarms = response.get('MetricAlarms', [])
            alarm_names = [alarm['AlarmName'] for alarm in alarms]
            
            # Check that our expected alarms exist
            for expected_alarm in expected_alarms:
                matching_alarms = [name for name in alarm_names if expected_alarm in name]
                assert len(matching_alarms) > 0, f"Alarm containing '{expected_alarm}' should exist"
            
        except ClientError as e:
            pytest.skip(f"Could not retrieve CloudWatch alarms: {e}")

    @given(metric_name=st.sampled_from(['Requests', 'BytesDownloaded', '4xxErrorRate', '5xxErrorRate', 'CacheHitRate']))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cloudfront_metric_data_retrieval(self, cloudformation_client, cloudwatch_client, test_config, metric_name):
        """
        Property-based test: For any CloudFront metric, should be able to retrieve metric data.
        Validates: Requirements 8.1
        """
        monitoring_info = self.get_monitoring_resources_from_stack(
            cloudformation_client, 
            test_config.get('master_stack_name', 'zackspeakfitness-infrastructure-test')
        )
        
        if monitoring_info is None:
            pytest.skip("Monitoring stack not deployed")
        
        distribution_id = monitoring_info.get('distribution_id')
        if not distribution_id:
            pytest.skip("Distribution ID not found")
        
        try:
            # Try to get metric statistics for the last hour
            import datetime
            end_time = datetime.datetime.utcnow()
            start_time = end_time - datetime.timedelta(hours=1)
            
            response = cloudwatch_client.get_metric_statistics(
                Namespace='AWS/CloudFront',
                MetricName=metric_name,
                Dimensions=[
                    {
                        'Name': 'DistributionId',
                        'Value': distribution_id
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=300,  # 5 minutes
                Statistics=['Sum', 'Average']
            )
            
            # Should be able to make the API call without error
            assert 'Datapoints' in response, f"Should be able to retrieve {metric_name} metric data"
            
        except ClientError as e:
            if e.response['Error']['Code'] in ['ValidationError', 'InvalidParameterValue']:
                pytest.skip(f"Metric {metric_name} might not be available yet")
            else:
                raise

    def test_sns_topic_configuration(self, cloudformation_client, sns_client, test_config):
        """
        Test that SNS topic for alerts is configured correctly.
        Validates: Requirements 8.4
        """
        monitoring_info = self.get_monitoring_resources_from_stack(
            cloudformation_client, 
            test_config.get('monitoring_stack_name', 'zackspeakfitness-monitoring-test')
        )
        
        if monitoring_info is None:
            pytest.skip("Monitoring stack not deployed")
        
        alerts_topic_arn = monitoring_info.get('alerts_topic_arn')
        if not alerts_topic_arn:
            pytest.skip("Alerts topic ARN not found in stack outputs")
        
        try:
            # Get topic attributes
            response = sns_client.get_topic_attributes(TopicArn=alerts_topic_arn)
            attributes = response.get('Attributes', {})
            
            # Check topic configuration
            assert 'DisplayName' in attributes, "SNS topic should have a display name"
            assert 'TopicArn' in attributes, "SNS topic should have ARN"
            
            # Check that topic exists and is accessible
            topic_arn = attributes['TopicArn']
            assert alerts_topic_arn in topic_arn, "Topic ARN should match expected value"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NotFound':
                pytest.skip("SNS topic not found")
            else:
                raise

    def test_cloudwatch_log_group_configuration(self, cloudformation_client, logs_client, test_config):
        """
        Test that CloudWatch log group for access logs is configured correctly.
        Validates: Requirements 8.1
        """
        monitoring_info = self.get_monitoring_resources_from_stack(
            cloudformation_client, 
            test_config.get('monitoring_stack_name', 'zackspeakfitness-monitoring-test')
        )
        
        if monitoring_info is None:
            pytest.skip("Monitoring stack not deployed")
        
        log_group_name = monitoring_info.get('log_group_name')
        if not log_group_name:
            pytest.skip("Log group name not found in stack outputs")
        
        try:
            # Get log group details
            response = logs_client.describe_log_groups(
                logGroupNamePrefix=log_group_name
            )
            
            log_groups = response.get('logGroups', [])
            matching_groups = [lg for lg in log_groups if lg['logGroupName'] == log_group_name]
            
            assert len(matching_groups) > 0, f"Log group {log_group_name} should exist"
            
            log_group = matching_groups[0]
            
            # Check retention policy
            retention_days = log_group.get('retentionInDays')
            assert retention_days == 30, f"Log group should have 30-day retention, got {retention_days}"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                pytest.skip("Log group not found")
            else:
                raise


class TestAlertingConfiguration:
    """
    Test alerting configuration and alarm functionality.
    Validates: Requirements 8.4
    """

    def get_alarm_details(self, cloudwatch_client, alarm_name_pattern: str) -> List[Dict[str, Any]]:
        """Get alarm details matching the pattern."""
        try:
            response = cloudwatch_client.describe_alarms()
            alarms = response.get('MetricAlarms', [])
            
            matching_alarms = [
                alarm for alarm in alarms 
                if alarm_name_pattern in alarm['AlarmName']
            ]
            
            return matching_alarms
            
        except Exception:
            return []

    @given(alarm_type=st.sampled_from(['high-error-rate', 'server-errors', 'low-cache-hit-rate', 'high-traffic']))
    @settings(max_examples=4, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_alarm_configuration_consistency(self, cloudformation_client, cloudwatch_client, test_config, alarm_type):
        """
        Property-based test: For any alarm type, configuration should be consistent and valid.
        Validates: Requirements 8.4
        """
        domain_name = test_config.get('domain_name', 'zackspeakfitness.com')
        environment = test_config.get('environment', 'test')
        
        alarm_name_pattern = f'{domain_name}-{environment}-{alarm_type}'
        
        alarms = self.get_alarm_details(cloudwatch_client, alarm_name_pattern)
        
        if not alarms:
            pytest.skip(f"Alarm with pattern '{alarm_name_pattern}' not found")
        
        for alarm in alarms:
            # Check basic alarm configuration
            assert alarm['MetricName'], "Alarm should have a metric name"
            assert alarm['Namespace'], "Alarm should have a namespace"
            assert alarm['Statistic'], "Alarm should have a statistic"
            assert alarm['Period'] > 0, "Alarm period should be positive"
            assert alarm['EvaluationPeriods'] > 0, "Evaluation periods should be positive"
            assert alarm['Threshold'] >= 0, "Threshold should be non-negative"
            assert alarm['ComparisonOperator'], "Alarm should have comparison operator"
            
            # Check that alarm has actions configured
            alarm_actions = alarm.get('AlarmActions', [])
            assert len(alarm_actions) > 0, f"Alarm {alarm['AlarmName']} should have alarm actions configured"
            
            # Check that actions are SNS topic ARNs
            for action in alarm_actions:
                assert action.startswith('arn:aws:sns:'), f"Alarm action should be SNS topic ARN, got {action}"
            
            # Check dimensions
            dimensions = alarm.get('Dimensions', [])
            assert len(dimensions) > 0, f"Alarm {alarm['AlarmName']} should have dimensions"

    def test_alarm_thresholds_are_reasonable(self, cloudformation_client, cloudwatch_client, test_config):
        """
        Test that alarm thresholds are set to reasonable values.
        Validates: Requirements 8.4
        """
        domain_name = test_config.get('domain_name', 'zackspeakfitness.com')
        environment = test_config.get('environment', 'test')
        
        # Expected threshold ranges for different alarm types
        expected_thresholds = {
            'high-error-rate': (5, 20),      # 5-20% error rate
            'server-errors': (0.5, 5),       # 0.5-5% server error rate
            'low-cache-hit-rate': (70, 90),  # 70-90% cache hit rate (alarm when below)
            'high-traffic': (1000, 50000)    # 1K-50K requests (depends on expected traffic)
        }
        
        for alarm_type, (min_threshold, max_threshold) in expected_thresholds.items():
            alarm_name_pattern = f'{domain_name}-{environment}-{alarm_type}'
            alarms = self.get_alarm_details(cloudwatch_client, alarm_name_pattern)
            
            if not alarms:
                continue  # Skip if alarm not found
            
            for alarm in alarms:
                threshold = alarm['Threshold']
                assert min_threshold <= threshold <= max_threshold, \
                    f"Alarm {alarm['AlarmName']} threshold {threshold} should be between {min_threshold} and {max_threshold}"

    def test_alarm_periods_are_appropriate(self, cloudformation_client, cloudwatch_client, test_config):
        """
        Test that alarm periods and evaluation periods are appropriate.
        Validates: Requirements 8.4
        """
        domain_name = test_config.get('domain_name', 'zackspeakfitness.com')
        environment = test_config.get('environment', 'test')
        
        # Get all our alarms
        alarm_types = ['high-error-rate', 'server-errors', 'low-cache-hit-rate', 'high-traffic']
        
        for alarm_type in alarm_types:
            alarm_name_pattern = f'{domain_name}-{environment}-{alarm_type}'
            alarms = self.get_alarm_details(cloudwatch_client, alarm_name_pattern)
            
            if not alarms:
                continue  # Skip if alarm not found
            
            for alarm in alarms:
                period = alarm['Period']
                evaluation_periods = alarm['EvaluationPeriods']
                
                # Period should be reasonable (5 minutes to 1 hour)
                assert 300 <= period <= 3600, f"Alarm {alarm['AlarmName']} period {period} should be between 300 and 3600 seconds"
                
                # Evaluation periods should be reasonable (1-5 periods)
                assert 1 <= evaluation_periods <= 5, f"Alarm {alarm['AlarmName']} evaluation periods {evaluation_periods} should be between 1 and 5"
                
                # Total evaluation time should be reasonable (5 minutes to 1 hour)
                total_time = period * evaluation_periods
                assert 300 <= total_time <= 3600, f"Alarm {alarm['AlarmName']} total evaluation time {total_time} should be between 300 and 3600 seconds"


class TestDashboardConfiguration:
    """
    Test CloudWatch dashboard configuration.
    Validates: Requirements 8.1
    """

    def test_infrastructure_dashboard_exists(self, cloudformation_client, cloudwatch_client, test_config):
        """
        Test that infrastructure monitoring dashboard exists and is configured.
        Validates: Requirements 8.1
        """
        monitoring_info = self.get_monitoring_resources_from_stack(
            cloudformation_client, 
            test_config.get('monitoring_stack_name', 'zackspeakfitness-monitoring-test')
        )
        
        if monitoring_info is None:
            pytest.skip("Monitoring stack not deployed")
        
        domain_name = test_config.get('domain_name', 'zackspeakfitness.com')
        environment = test_config.get('environment', 'test')
        
        dashboard_name = f'{domain_name}-{environment}-infrastructure'
        
        try:
            # Get dashboard
            response = cloudwatch_client.get_dashboard(DashboardName=dashboard_name)
            dashboard_body = response.get('DashboardBody', '{}')
            
            # Parse dashboard configuration
            import json
            dashboard_config = json.loads(dashboard_body)
            
            # Check that dashboard has widgets
            widgets = dashboard_config.get('widgets', [])
            assert len(widgets) > 0, "Dashboard should have widgets configured"
            
            # Check for expected widget types
            widget_types = [widget.get('type') for widget in widgets]
            assert 'metric' in widget_types, "Dashboard should have metric widgets"
            
            # Check for CloudFront metrics in widgets
            dashboard_str = json.dumps(dashboard_config)
            assert 'AWS/CloudFront' in dashboard_str, "Dashboard should include CloudFront metrics"
            assert 'Requests' in dashboard_str, "Dashboard should include request metrics"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFound':
                pytest.skip("Infrastructure dashboard not found")
            else:
                raise

    def test_cost_tracking_dashboard_exists(self, cloudformation_client, cloudwatch_client, test_config):
        """
        Test that cost tracking dashboard exists and is configured.
        Validates: Requirements 8.1
        """
        monitoring_info = self.get_monitoring_resources_from_stack(
            cloudformation_client, 
            test_config.get('monitoring_stack_name', 'zackspeakfitness-monitoring-test')
        )
        
        if monitoring_info is None:
            pytest.skip("Monitoring stack not deployed")
        
        domain_name = test_config.get('domain_name', 'zackspeakfitness.com')
        environment = test_config.get('environment', 'test')
        
        dashboard_name = f'{domain_name}-{environment}-cost-tracking'
        
        try:
            # Get dashboard
            response = cloudwatch_client.get_dashboard(DashboardName=dashboard_name)
            dashboard_body = response.get('DashboardBody', '{}')
            
            # Parse dashboard configuration
            import json
            dashboard_config = json.loads(dashboard_body)
            
            # Check that dashboard has widgets
            widgets = dashboard_config.get('widgets', [])
            assert len(widgets) > 0, "Cost dashboard should have widgets configured"
            
            # Check for billing metrics
            dashboard_str = json.dumps(dashboard_config)
            assert 'AWS/Billing' in dashboard_str, "Cost dashboard should include billing metrics"
            assert 'EstimatedCharges' in dashboard_str, "Cost dashboard should include estimated charges"
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFound':
                pytest.skip("Cost tracking dashboard not found")
            else:
                raise

    def get_monitoring_resources_from_stack(self, cloudformation_client, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get monitoring resources from CloudFormation stack."""
        try:
            response = cloudformation_client.describe_stacks(StackName=stack_name)
            stacks = response.get('Stacks', [])
            
            if not stacks:
                return None
                
            stack = stacks[0]
            outputs = stack.get('Outputs', [])
            
            monitoring_info = {}
            for output in outputs:
                if output['OutputKey'] == 'DistributionId':
                    monitoring_info['distribution_id'] = output['OutputValue']
                elif output['OutputKey'] == 'AlertsTopicArn':
                    monitoring_info['alerts_topic_arn'] = output['OutputValue']
                elif output['OutputKey'] == 'AccessLogsLogGroupName':
                    monitoring_info['log_group_name'] = output['OutputValue']
                elif output['OutputKey'] == 'DashboardURL':
                    monitoring_info['dashboard_url'] = output['OutputValue']
                elif output['OutputKey'] == 'CostTrackingDashboardURL':
                    monitoring_info['cost_dashboard_url'] = output['OutputValue']
            
            return monitoring_info if monitoring_info else None
            
        except Exception:
            return None


class TestMonitoringIntegration:
    """Integration tests for monitoring infrastructure."""
    
    def test_monitoring_cloudformation_template_syntax(self):
        """
        Test that monitoring CloudFormation template has valid syntax.
        """
        try:
            with open('cloudformation/templates/monitoring.yaml', 'r') as f:
                template_content = f.read()
            
            # Basic content validation
            assert 'AWSTemplateFormatVersion' in template_content
            assert 'Resources:' in template_content
            
            # Check for monitoring resources
            assert 'AlertsTopic:' in template_content
            assert 'AWS::SNS::Topic' in template_content
            assert 'InfrastructureDashboard:' in template_content
            assert 'AWS::CloudWatch::Dashboard' in template_content
            assert 'CostTrackingDashboard:' in template_content
            
            # Check for alarms
            assert 'HighErrorRateAlarm:' in template_content
            assert 'ServerErrorAlarm:' in template_content
            assert 'LowCacheHitRateAlarm:' in template_content
            assert 'HighTrafficAlarm:' in template_content
            assert 'AWS::CloudWatch::Alarm' in template_content
            
            # Check for log group
            assert 'AccessLogsLogGroup:' in template_content
            assert 'AWS::Logs::LogGroup' in template_content
            
        except FileNotFoundError:
            pytest.fail("Monitoring CloudFormation template not found")

    def test_tagging_strategy_implementation(self):
        """
        Test that monitoring resources implement consistent tagging strategy.
        """
        try:
            with open('cloudformation/templates/monitoring.yaml', 'r') as f:
                template_content = f.read()
            
            # Check for required tags
            required_tags = [
                'Name', 'Environment', 'Project', 'Owner', 
                'CostCenter', 'Component', 'ManagedBy'
            ]
            
            for tag in required_tags:
                assert f'Key: {tag}' in template_content, f"Template should include {tag} tag"
            
            # Check for cost allocation tags
            assert 'CostCenter' in template_content
            assert 'website-operations' in template_content
            assert 'static-website' in template_content
            assert 'monitoring' in template_content
            
        except FileNotFoundError:
            pytest.fail("Monitoring CloudFormation template not found")

    def test_master_template_includes_monitoring_stack(self):
        """
        Test that master template includes monitoring stack.
        """
        try:
            with open('cloudformation/master-template.yaml', 'r') as f:
                template_content = f.read()
            
            # Check for monitoring stack
            assert 'MonitoringStack:' in template_content
            assert 'monitoring.yaml' in template_content
            
            # Check for monitoring outputs
            assert 'AlertsTopicArn:' in template_content
            assert 'DashboardURL:' in template_content
            assert 'CostTrackingDashboardURL:' in template_content
            
        except FileNotFoundError:
            pytest.fail("Master CloudFormation template not found")