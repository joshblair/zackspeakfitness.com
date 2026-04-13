#!/usr/bin/env python3
"""
Simple CloudFormation template validation script.
Validates basic structure without requiring AWS credentials.
"""

import os
import sys
import yaml
from typing import List, Tuple


def validate_cloudformation_template(template_path: str) -> Tuple[bool, str]:
    """Validate a CloudFormation template for basic structure."""
    try:
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Check for required CloudFormation sections
        required_sections = ['AWSTemplateFormatVersion', 'Resources']
        for section in required_sections:
            if section not in content:
                return False, f"Missing required section: {section}"
        
        # Check for valid AWSTemplateFormatVersion
        if "'2010-09-09'" not in content and '"2010-09-09"' not in content:
            return False, "Invalid or missing AWSTemplateFormatVersion"
        
        # Try to parse as YAML with CloudFormation constructors
        try:
            # Add CloudFormation constructors to YAML loader
            class CloudFormationLoader(yaml.SafeLoader):
                pass
            
            def construct_ref(loader, node):
                return {'Ref': loader.construct_scalar(node)}
            
            def construct_getatt(loader, node):
                if isinstance(node, yaml.ScalarNode):
                    return {'Fn::GetAtt': loader.construct_scalar(node)}
                elif isinstance(node, yaml.SequenceNode):
                    return {'Fn::GetAtt': loader.construct_sequence(node)}
                else:
                    return {'Fn::GetAtt': loader.construct_mapping(node)}
            
            def construct_sub(loader, node):
                return {'Fn::Sub': loader.construct_scalar(node)}
            
            def construct_equals(loader, node):
                return {'Fn::Equals': loader.construct_sequence(node)}
            
            def construct_if(loader, node):
                return {'Fn::If': loader.construct_sequence(node)}
            
            def construct_not(loader, node):
                return {'Fn::Not': loader.construct_sequence(node)}
            
            def construct_and(loader, node):
                return {'Fn::And': loader.construct_sequence(node)}
            
            def construct_or(loader, node):
                return {'Fn::Or': loader.construct_sequence(node)}
            
            def construct_join(loader, node):
                return {'Fn::Join': loader.construct_sequence(node)}
            
            # Register CloudFormation constructors
            CloudFormationLoader.add_constructor('!Ref', construct_ref)
            CloudFormationLoader.add_constructor('!GetAtt', construct_getatt)
            CloudFormationLoader.add_constructor('!Sub', construct_sub)
            CloudFormationLoader.add_constructor('!Equals', construct_equals)
            CloudFormationLoader.add_constructor('!If', construct_if)
            CloudFormationLoader.add_constructor('!Not', construct_not)
            CloudFormationLoader.add_constructor('!And', construct_and)
            CloudFormationLoader.add_constructor('!Or', construct_or)
            CloudFormationLoader.add_constructor('!Join', construct_join)
            
            # Parse the template
            yaml.load(content, Loader=CloudFormationLoader)
            
        except yaml.YAMLError as e:
            return False, f"YAML parsing error: {e}"
        
        return True, "Template structure is valid"
        
    except FileNotFoundError:
        return False, f"Template file not found: {template_path}"
    except Exception as e:
        return False, f"Error validating template: {e}"


def main():
    """Validate all CloudFormation templates."""
    template_files = [
        'master-template.yaml',
        'templates/certificate.yaml',
        'templates/storage.yaml',
        'templates/distribution.yaml',
        'templates/dns.yaml',
        'templates/cicd.yaml'
    ]
    
    all_valid = True
    
    print("Validating CloudFormation templates...")
    print("=" * 50)
    
    for template_file in template_files:
        if os.path.exists(template_file):
            is_valid, message = validate_cloudformation_template(template_file)
            status = "✓" if is_valid else "✗"
            print(f"{status} {template_file}: {message}")
            
            if not is_valid:
                all_valid = False
        else:
            print(f"✗ {template_file}: File not found")
            all_valid = False
    
    print("=" * 50)
    if all_valid:
        print("✓ All templates are valid!")
        sys.exit(0)
    else:
        print("✗ Some templates have validation errors!")
        sys.exit(1)


if __name__ == '__main__':
    main()