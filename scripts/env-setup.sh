#!/bin/bash
# Run this at the start of every new Git Bash session:
#   source scripts/env-setup.sh

# Clear any shell-level AWS profile override (can point to an expired SSO profile)
unset AWS_PROFILE
unset AWS_ACCESS_KEY_ID
unset AWS_SECRET_ACCESS_KEY
unset AWS_SESSION_TOKEN

# Verify the ptab profile works
echo "Checking AWS credentials..."
aws sts get-caller-identity --profile ptab

echo ""
echo "Ready. You're in account: $(aws sts get-caller-identity --profile ptab --query Account --output text)"
