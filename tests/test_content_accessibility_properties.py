"""
Property-based tests for content accessibility validation.
Feature: static-website-infrastructure, Property 7: Content Accessibility
"""
import pytest
import requests
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import List, Dict, Any, Optional
import os
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time


class TestContentAccessibility:
    """
    Property 7: Content Accessibility
    For any static file in the website directory, it should be accessible via HTTPS 
    through the CloudFront distribution
    Validates: Requirements 1.1, 1.3
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
            
            # Find distribution domain from outputs
            distribution_info = {}
            for output in outputs:
                if output['OutputKey'] == 'DistributionDomainName':
                    distribution_info['domain_name'] = output['OutputValue']
                elif output['OutputKey'] == 'DistributionId':
                    distribution_info['distribution_id'] = output['OutputValue']
                elif output['OutputKey'] == 'CustomDomainName':
                    distribution_info['custom_domain'] = output['OutputValue']
            
            return distribution_info if distribution_info else None
            
        except Exception:
            return None

    def get_website_files(self) -> List[str]:
        """Get list of static files from website directory."""
        website_files = []
        website_dir = 'website'
        
        if not os.path.exists(website_dir):
            return []
        
        for root, dirs, files in os.walk(website_dir):
            for file in files:
                # Skip hidden files and directories
                if file.startswith('.'):
                    continue
                    
                # Get relative path from website directory
                rel_path = os.path.relpath(os.path.join(root, file), website_dir)
                # Convert to URL path (use forward slashes)
                url_path = rel_path.replace(os.sep, '/')
                website_files.append(url_path)
        
        return website_files

    def test_html_files_accessible_via_https(self, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Test that all HTML files are accessible via HTTPS through CloudFront.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        # Get HTML files from website directory
        website_files = self.get_website_files()
        html_files = [f for f in website_files if f.endswith('.html')]
        
        if not html_files:
            pytest.skip("No HTML files found in website directory")
        
        # Test each HTML file
        for html_file in html_files:
            url = f"https://{domain}/{html_file}"
            
            try:
                response = requests.get(url, timeout=30, allow_redirects=True)
                
                # Should be accessible (200 OK)
                assert response.status_code == 200, f"HTML file {html_file} should be accessible, got status {response.status_code}"
                
                # Should be served over HTTPS
                assert response.url.startswith('https://'), f"HTML file {html_file} should be served over HTTPS"
                
                # Should have HTML content type
                content_type = response.headers.get('content-type', '').lower()
                assert 'text/html' in content_type, f"HTML file {html_file} should have HTML content type, got {content_type}"
                
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Failed to access HTML file {html_file}: {e}")

    def test_css_files_accessible_via_https(self, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Test that all CSS files are accessible via HTTPS through CloudFront.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        # Get CSS files from website directory
        website_files = self.get_website_files()
        css_files = [f for f in website_files if f.endswith('.css')]
        
        if not css_files:
            pytest.skip("No CSS files found in website directory")
        
        # Test each CSS file
        for css_file in css_files:
            url = f"https://{domain}/{css_file}"
            
            try:
                response = requests.get(url, timeout=30, allow_redirects=True)
                
                # Should be accessible (200 OK)
                assert response.status_code == 200, f"CSS file {css_file} should be accessible, got status {response.status_code}"
                
                # Should be served over HTTPS
                assert response.url.startswith('https://'), f"CSS file {css_file} should be served over HTTPS"
                
                # Should have CSS content type
                content_type = response.headers.get('content-type', '').lower()
                assert 'text/css' in content_type or 'text/plain' in content_type, f"CSS file {css_file} should have CSS content type, got {content_type}"
                
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Failed to access CSS file {css_file}: {e}")

    def test_javascript_files_accessible_via_https(self, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Test that all JavaScript files are accessible via HTTPS through CloudFront.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        # Get JavaScript files from website directory
        website_files = self.get_website_files()
        js_files = [f for f in website_files if f.endswith('.js')]
        
        if not js_files:
            pytest.skip("No JavaScript files found in website directory")
        
        # Test each JavaScript file
        for js_file in js_files:
            url = f"https://{domain}/{js_file}"
            
            try:
                response = requests.get(url, timeout=30, allow_redirects=True)
                
                # Should be accessible (200 OK)
                assert response.status_code == 200, f"JavaScript file {js_file} should be accessible, got status {response.status_code}"
                
                # Should be served over HTTPS
                assert response.url.startswith('https://'), f"JavaScript file {js_file} should be served over HTTPS"
                
                # Should have JavaScript content type
                content_type = response.headers.get('content-type', '').lower()
                assert any(ct in content_type for ct in ['application/javascript', 'text/javascript', 'application/x-javascript']), \
                    f"JavaScript file {js_file} should have JavaScript content type, got {content_type}"
                
            except requests.exceptions.RequestException as e:
                pytest.fail(f"Failed to access JavaScript file {js_file}: {e}")

    @given(file_path=st.sampled_from(['index.html', 'about.html', 'services.html', 'contact.html', 'testimonials.html']))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_html_pages_have_proper_structure(self, cloudformation_client, test_config, file_path):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Property-based test: For any HTML page, it should have proper HTML structure and accessibility features.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        url = f"https://{domain}/{file_path}"
        
        try:
            response = requests.get(url, timeout=30, allow_redirects=True)
            
            # Should be accessible
            assert response.status_code == 200, f"Page {file_path} should be accessible"
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Basic HTML structure validation
            assert soup.find('html'), f"Page {file_path} should have <html> tag"
            assert soup.find('head'), f"Page {file_path} should have <head> tag"
            assert soup.find('body'), f"Page {file_path} should have <body> tag"
            assert soup.find('title'), f"Page {file_path} should have <title> tag"
            
            # Accessibility validation
            assert soup.find('html').get('lang'), f"Page {file_path} should have lang attribute on <html> tag"
            
            # Meta tags validation
            meta_charset = soup.find('meta', {'charset': True})
            meta_viewport = soup.find('meta', {'name': 'viewport'})
            meta_description = soup.find('meta', {'name': 'description'})
            
            assert meta_charset, f"Page {file_path} should have charset meta tag"
            assert meta_viewport, f"Page {file_path} should have viewport meta tag"
            assert meta_description, f"Page {file_path} should have description meta tag"
            
            # Navigation validation
            nav = soup.find('nav')
            assert nav, f"Page {file_path} should have navigation"
            
            # Check for proper heading hierarchy
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            assert len(headings) > 0, f"Page {file_path} should have headings"
            
            # Should have at least one h1
            h1_tags = soup.find_all('h1')
            assert len(h1_tags) >= 1, f"Page {file_path} should have at least one h1 tag"
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access page {file_path}: {e}")

    def test_images_have_alt_attributes(self, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Test that all images have alt attributes for accessibility.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        # Get HTML files from website directory
        website_files = self.get_website_files()
        html_files = [f for f in website_files if f.endswith('.html')]
        
        if not html_files:
            pytest.skip("No HTML files found in website directory")
        
        # Check each HTML file for image accessibility
        for html_file in html_files:
            url = f"https://{domain}/{html_file}"
            
            try:
                response = requests.get(url, timeout=30, allow_redirects=True)
                
                if response.status_code != 200:
                    continue  # Skip if page not accessible
                
                # Parse HTML content
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all img tags
                images = soup.find_all('img')
                
                for img in images:
                    # Each image should have an alt attribute
                    assert img.get('alt') is not None, f"Image in {html_file} missing alt attribute: {img}"
                    
                    # Alt text should not be empty for content images
                    # (decorative images can have empty alt text)
                    alt_text = img.get('alt', '').strip()
                    src = img.get('src', '')
                    
                    # If it's not a decorative image, it should have meaningful alt text
                    if not any(keyword in src.lower() for keyword in ['decoration', 'spacer', 'divider']):
                        if alt_text == '':
                            # Empty alt is only acceptable for decorative images
                            # Check if image has role="presentation" or is in a decorative context
                            role = img.get('role')
                            if role != 'presentation':
                                pytest.fail(f"Content image in {html_file} has empty alt text: {img}")
                
            except requests.exceptions.RequestException:
                # Skip if page not accessible
                continue

    def test_forms_have_proper_labels(self, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Test that all form inputs have proper labels for accessibility.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        # Test contact page specifically (has forms)
        url = f"https://{domain}/contact.html"
        
        try:
            response = requests.get(url, timeout=30, allow_redirects=True)
            
            if response.status_code != 200:
                pytest.skip("Contact page not accessible")
            
            # Parse HTML content
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all form inputs
            inputs = soup.find_all(['input', 'select', 'textarea'])
            
            for input_elem in inputs:
                input_type = input_elem.get('type', 'text')
                input_id = input_elem.get('id')
                input_name = input_elem.get('name')
                
                # Skip hidden inputs and buttons
                if input_type in ['hidden', 'submit', 'button']:
                    continue
                
                # Each input should have an associated label
                label = None
                
                # Method 1: Label with 'for' attribute
                if input_id:
                    label = soup.find('label', {'for': input_id})
                
                # Method 2: Input wrapped in label
                if not label:
                    label = input_elem.find_parent('label')
                
                # Method 3: aria-label attribute
                if not label:
                    aria_label = input_elem.get('aria-label')
                    if aria_label:
                        label = True  # Has aria-label
                
                # Method 4: aria-labelledby attribute
                if not label:
                    aria_labelledby = input_elem.get('aria-labelledby')
                    if aria_labelledby:
                        referenced_elem = soup.find(id=aria_labelledby)
                        if referenced_elem:
                            label = True  # Has valid aria-labelledby
                
                assert label, f"Form input missing label: {input_elem} (id: {input_id}, name: {input_name})"
                
        except requests.exceptions.RequestException:
            pytest.skip("Contact page not accessible for form testing")

    @given(static_file=st.sampled_from(['css/main.css', 'css/responsive.css', 'js/main.js', 'js/analytics.js', 'assets/robots.txt']))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_static_assets_accessible_via_https(self, cloudformation_client, test_config, static_file):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Property-based test: For any static asset file, it should be accessible via HTTPS.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        url = f"https://{domain}/{static_file}"
        
        try:
            response = requests.get(url, timeout=30, allow_redirects=True)
            
            # Should be accessible (200 OK)
            assert response.status_code == 200, f"Static file {static_file} should be accessible, got status {response.status_code}"
            
            # Should be served over HTTPS
            assert response.url.startswith('https://'), f"Static file {static_file} should be served over HTTPS"
            
            # Should have appropriate content type based on file extension
            content_type = response.headers.get('content-type', '').lower()
            
            if static_file.endswith('.css'):
                assert 'text/css' in content_type or 'text/plain' in content_type, \
                    f"CSS file {static_file} should have CSS content type, got {content_type}"
            elif static_file.endswith('.js'):
                assert any(ct in content_type for ct in ['application/javascript', 'text/javascript', 'application/x-javascript']), \
                    f"JavaScript file {static_file} should have JavaScript content type, got {content_type}"
            elif static_file.endswith('.txt'):
                assert 'text/plain' in content_type, \
                    f"Text file {static_file} should have text/plain content type, got {content_type}"
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Failed to access static file {static_file}: {e}")

    def test_security_headers_present(self, cloudformation_client, test_config):
        """
        Feature: static-website-infrastructure, Property 7: Content Accessibility
        Test that security headers are present in responses.
        """
        distribution_info = self.get_distribution_from_stack(
            cloudformation_client, 
            test_config['distribution_stack_name']
        )
        
        # Skip test if distribution stack doesn't exist
        if distribution_info is None:
            pytest.skip("Distribution stack not deployed or distribution not found")
        
        # Use custom domain if available, otherwise use CloudFront domain
        domain = distribution_info.get('custom_domain') or distribution_info.get('domain_name')
        if not domain:
            pytest.skip("Distribution domain not found in stack outputs")
        
        url = f"https://{domain}/index.html"
        
        try:
            response = requests.get(url, timeout=30, allow_redirects=True)
            
            if response.status_code != 200:
                pytest.skip("Homepage not accessible for security header testing")
            
            headers = response.headers
            
            # Check for security headers (these should be configured in CloudFront)
            expected_headers = {
                'strict-transport-security': 'HSTS header should be present',
                'x-content-type-options': 'X-Content-Type-Options header should be present',
                'x-frame-options': 'X-Frame-Options header should be present',
                'referrer-policy': 'Referrer-Policy header should be present'
            }
            
            for header_name, error_message in expected_headers.items():
                # Check if header is present (case-insensitive)
                header_present = any(header_name.lower() == key.lower() for key in headers.keys())
                assert header_present, f"{error_message} (header: {header_name})"
            
        except requests.exceptions.RequestException:
            pytest.skip("Homepage not accessible for security header testing")


class TestContentValidation:
    """Additional content validation tests."""
    
    def test_website_directory_structure_exists(self):
        """
        Test that website directory structure exists with required files.
        """
        website_dir = 'website'
        assert os.path.exists(website_dir), "Website directory should exist"
        
        # Check for required HTML files
        required_files = ['index.html', 'about.html', 'services.html', 'contact.html']
        for file_name in required_files:
            file_path = os.path.join(website_dir, file_name)
            assert os.path.exists(file_path), f"Required file {file_name} should exist"
        
        # Check for CSS directory and files
        css_dir = os.path.join(website_dir, 'css')
        assert os.path.exists(css_dir), "CSS directory should exist"
        
        required_css = ['main.css', 'responsive.css']
        for css_file in required_css:
            css_path = os.path.join(css_dir, css_file)
            assert os.path.exists(css_path), f"Required CSS file {css_file} should exist"
        
        # Check for JavaScript directory and files
        js_dir = os.path.join(website_dir, 'js')
        assert os.path.exists(js_dir), "JavaScript directory should exist"
        
        required_js = ['main.js', 'analytics.js']
        for js_file in required_js:
            js_path = os.path.join(js_dir, js_file)
            assert os.path.exists(js_path), f"Required JavaScript file {js_file} should exist"

    def test_html_files_have_valid_syntax(self):
        """
        Test that HTML files have valid basic syntax.
        """
        website_dir = 'website'
        if not os.path.exists(website_dir):
            pytest.skip("Website directory not found")
        
        html_files = []
        for root, dirs, files in os.walk(website_dir):
            for file in files:
                if file.endswith('.html'):
                    html_files.append(os.path.join(root, file))
        
        if not html_files:
            pytest.skip("No HTML files found")
        
        for html_file in html_files:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic HTML validation
            assert '<!DOCTYPE html>' in content, f"HTML file {html_file} should have DOCTYPE declaration"
            assert '<html' in content, f"HTML file {html_file} should have <html> tag"
            assert '<head>' in content, f"HTML file {html_file} should have <head> tag"
            assert '<body>' in content, f"HTML file {html_file} should have <body> tag"
            assert '<title>' in content, f"HTML file {html_file} should have <title> tag"
            assert '</html>' in content, f"HTML file {html_file} should have closing </html> tag"
            
            # Parse with BeautifulSoup for more detailed validation
            soup = BeautifulSoup(content, 'html.parser')
            
            # Check for required meta tags
            meta_charset = soup.find('meta', {'charset': True})
            meta_viewport = soup.find('meta', {'name': 'viewport'})
            
            assert meta_charset, f"HTML file {html_file} should have charset meta tag"
            assert meta_viewport, f"HTML file {html_file} should have viewport meta tag"

    def test_css_files_have_valid_syntax(self):
        """
        Test that CSS files have basic valid syntax.
        """
        website_dir = 'website'
        css_dir = os.path.join(website_dir, 'css')
        
        if not os.path.exists(css_dir):
            pytest.skip("CSS directory not found")
        
        css_files = []
        for file in os.listdir(css_dir):
            if file.endswith('.css'):
                css_files.append(os.path.join(css_dir, file))
        
        if not css_files:
            pytest.skip("No CSS files found")
        
        for css_file in css_files:
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic CSS validation
            assert len(content.strip()) > 0, f"CSS file {css_file} should not be empty"
            
            # Check for basic CSS structure (rules with selectors and properties)
            # This is a very basic check - for production, use a proper CSS parser
            has_css_rules = '{' in content and '}' in content
            assert has_css_rules, f"CSS file {css_file} should contain CSS rules"

    def test_javascript_files_have_valid_syntax(self):
        """
        Test that JavaScript files have basic valid syntax.
        """
        website_dir = 'website'
        js_dir = os.path.join(website_dir, 'js')
        
        if not os.path.exists(js_dir):
            pytest.skip("JavaScript directory not found")
        
        js_files = []
        for file in os.listdir(js_dir):
            if file.endswith('.js'):
                js_files.append(os.path.join(js_dir, file))
        
        if not js_files:
            pytest.skip("No JavaScript files found")
        
        for js_file in js_files:
            with open(js_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Basic JavaScript validation
            assert len(content.strip()) > 0, f"JavaScript file {js_file} should not be empty"
            
            # Check for basic JavaScript structure
            # This is a very basic check - for production, use a proper JS parser
            has_js_content = any(keyword in content for keyword in [
                'function', 'var', 'let', 'const', 'document', 'window'
            ])
            assert has_js_content, f"JavaScript file {js_file} should contain JavaScript code"