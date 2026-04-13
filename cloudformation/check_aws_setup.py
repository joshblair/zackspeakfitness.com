#!/usr/bin/env python3
"""
Check AWS setup and provide guidance for deployment.
"""

import boto3
import sys
from botocore.exceptions import NoCredentialsError, ClientError


def check_aws_credentials():
    """Check if AWS credentials are properly configured."""
    try:
        session = boto3.Session()
        credentials = session.get_credentials()
        
        if not credentials:
            return False, "No AWS credentials found"
        
        # Test credentials by making a simple API call
        sts_client = boto3.client('sts')
        response = sts_client.get_caller_identity()
        
        account_id = response.get('Account')
        user_arn = response.get('Arn')
        
        return True, f"Credentials valid - Account: {account_id}, User: {user_arn}"
        
    except NoCredentialsError:
        return False, "AWS credentials not configured"
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ExpiredToken':
            return False, "AWS credentials have expired"
        elif error_code == 'InvalidUserID.NotFound':
            return False, "AWS credentials are invalid"
        else:
            return False, f"AWS API error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def check_required_permissions():
    """Check if the current user has required permissions."""
    required_services = [
        ('cloudformation', 'CloudFormation'),
        ('s3', 'S3'),
        ('cloudfront', 'CloudFront'),
        ('route53', 'Route 53'),
        ('acm', 'Certificate Manager')
    ]
    
    permissions_ok = True
    
    print("Checking service access permissions...")
    
    for service, display_name in required_services:
        try:
            client = boto3.client(service)
            
            # Test basic read access for each service
            if service == 'cloudformation':
                client.list_stacks(MaxItems=1)
            elif service == 's3':
                client.list_buckets()
            elif service == 'cloudfront':
                client.list_distributions(MaxItems=1)
            elif service == 'route53':
                client.list_hosted_zones(MaxItems=1)
            elif service == 'acm':
                # ACM for CloudFront must be in us-east-1
                acm_client = boto3.client('acm', region_name='us-east-1')
                acm_client.list_certificates(MaxItems=1)
            
            print(f"✓ {display_name}: Access OK")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ['AccessDenied', 'UnauthorizedOperation']:
                print(f"✗ {display_name}: Access denied")
                permissions_ok = False
            else:
                print(f"⚠ {display_name}: {e}")
        except Exception as e:
            print(f"⚠ {display_name}: {e}")
    
    return permissions_ok


def main():
    """Main function to check AWS setup."""
    print("AWS Setup Validation")
    print("=" * 40)
    
    # Check credentials
    creds_valid, creds_message = check_aws_credentials()
    
    if creds_valid:
        print(f"✓ AWS Credentials: {creds_message}")
        
        # Check permissions
        perms_ok = check_required_permissions()
        
        if perms_ok:
            print("\n✓ AWS setup is ready for deployment!")
            print("\nNext steps:")
            print("1. Run: python deploy_test_environment.py")
            print("2. Or run: python deploy.py --stack-name your-stack-name --environment dev")
            return True
        else:
            print("\n✗ Some permissions are missing.")
            print("Please ensure your AWS user/role has the following permissions:")
            print("- CloudFormation: Full access")
            print("- S3: Full access") 
            print("- CloudFront: Full access")
            print("- Route 53: Full access")
            print("- ACM: Full access")
            return False
    else:
        print(f"✗ AWS Credentials: {creds_message}")
        print("\nTo configure AWS credentials, choose one of these options:")
        print("\n1. AWS CLI (recommended):")
        print("   aws configure")
        print("\n2. Environment variables:")
        print("   export AWS_ACCESS_KEY_ID=your_access_key")
        print("   export AWS_SECRET_ACCESS_KEY=your_secret_key")
        print("   export AWS_DEFAULT_REGION=us-west-2")
        print("\n3. IAM roles (for EC2/Lambda):")
        print("   Attach appropriate IAM role to your instance")
        print("\n4. AWS credentials file:")
        print("   Create ~/.aws/credentials with your keys")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)