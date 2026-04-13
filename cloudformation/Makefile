# Makefile for Static Website Infrastructure Deployment

# Default values
STACK_NAME ?= zackspeakfitness-prod
ENVIRONMENT ?= prod
TEMPLATE_BUCKET ?= your-cloudformation-templates-bucket
REGION ?= us-west-2

# Python virtual environment
VENV_DIR = .venv
PYTHON = $(VENV_DIR)/bin/python
PIP = $(VENV_DIR)/bin/pip

.PHONY: help install validate deploy update delete clean upload-templates status outputs

help: ## Show this help message
	@echo "Static Website Infrastructure Deployment"
	@echo "========================================"
	@echo ""
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
	@echo ""
	@echo "Environment variables:"
	@echo "  STACK_NAME      CloudFormation stack name (default: $(STACK_NAME))"
	@echo "  ENVIRONMENT     Environment: dev, staging, prod (default: $(ENVIRONMENT))"
	@echo "  TEMPLATE_BUCKET S3 bucket for templates (default: $(TEMPLATE_BUCKET))"
	@echo "  REGION          AWS region (default: $(REGION))"

install: $(VENV_DIR) ## Install Python dependencies
	$(PIP) install -r requirements.txt

$(VENV_DIR):
	python3 -m venv $(VENV_DIR)
	$(PIP) install --upgrade pip

validate: install ## Validate CloudFormation templates
	@echo "Validating CloudFormation templates..."
	@for template in templates/*.yaml master-template.yaml; do \
		echo "Validating $$template..."; \
		aws cloudformation validate-template --template-body file://$$template --region $(REGION) > /dev/null; \
		echo "✓ $$template is valid"; \
	done
	@echo "All templates validated successfully!"

lint: ## Lint CloudFormation templates (requires cfn-lint)
	@echo "Linting CloudFormation templates..."
	@if command -v cfn-lint >/dev/null 2>&1; then \
		cfn-lint templates/*.yaml master-template.yaml; \
	else \
		echo "cfn-lint not installed. Install with: pip install cfn-lint"; \
	fi

upload-templates: install ## Upload nested templates to S3
	$(PYTHON) deploy.py \
		--stack-name $(STACK_NAME) \
		--environment $(ENVIRONMENT) \
		--template-bucket $(TEMPLATE_BUCKET) \
		--region $(REGION) \
		--upload-templates

deploy: install ## Deploy the complete infrastructure
	$(PYTHON) deploy.py \
		--stack-name $(STACK_NAME) \
		--environment $(ENVIRONMENT) \
		--template-bucket $(TEMPLATE_BUCKET) \
		--region $(REGION) \
		--upload-templates

update: install ## Update existing infrastructure
	$(PYTHON) deploy.py \
		--stack-name $(STACK_NAME) \
		--environment $(ENVIRONMENT) \
		--template-bucket $(TEMPLATE_BUCKET) \
		--region $(REGION)

delete: install ## Delete the infrastructure stack
	$(PYTHON) deploy.py \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--delete

status: ## Show stack status
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'Stacks[0].StackStatus' \
		--output text 2>/dev/null || echo "Stack not found"

outputs: ## Show stack outputs
	@aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
		--output table 2>/dev/null || echo "Stack not found or no outputs"

events: ## Show recent stack events
	@aws cloudformation describe-stack-events \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'StackEvents[0:10].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId,ResourceStatusReason]' \
		--output table 2>/dev/null || echo "Stack not found"

resources: ## List stack resources
	@aws cloudformation list-stack-resources \
		--stack-name $(STACK_NAME) \
		--region $(REGION) \
		--query 'StackResourceSummaries[*].[LogicalResourceId,ResourceType,ResourceStatus]' \
		--output table 2>/dev/null || echo "Stack not found"

clean: ## Clean up local files
	rm -rf $(VENV_DIR)
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Development shortcuts
dev-deploy: ## Deploy to development environment
	$(MAKE) deploy ENVIRONMENT=dev STACK_NAME=zackspeakfitness-dev

staging-deploy: ## Deploy to staging environment
	$(MAKE) deploy ENVIRONMENT=staging STACK_NAME=zackspeakfitness-staging

prod-deploy: ## Deploy to production environment
	$(MAKE) deploy ENVIRONMENT=prod STACK_NAME=zackspeakfitness-prod

# Quick status checks
dev-status: ## Check development stack status
	$(MAKE) status STACK_NAME=zackspeakfitness-dev

staging-status: ## Check staging stack status
	$(MAKE) status STACK_NAME=zackspeakfitness-staging

prod-status: ## Check production stack status
	$(MAKE) status STACK_NAME=zackspeakfitness-prod