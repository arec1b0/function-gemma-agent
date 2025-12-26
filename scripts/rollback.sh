#!/bin/bash

# FunctionGemma Agent Rollback Script
# This script provides a quick rollback mechanism for failed deployments

set -euo pipefail

# Default values
NAMESPACE="production"
RELEASE_NAME="function-gemma-agent"
REVISION=0

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -n, --namespace NAMESPACE    Kubernetes namespace (default: production)"
    echo "  -r, --release RELEASE_NAME    Helm release name (default: function-gemma-agent)"
    echo "  -v, --revision REVISION       Revision to rollback to (default: 0, previous version)"
    echo "  -h, --help                   Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Rollback to previous version"
    echo "  $0 -v 2                      # Rollback to revision 2"
    echo "  $0 -n staging -r agent-staging -v 5  # Rollback staging release to revision 5"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -r|--release)
            RELEASE_NAME="$2"
            shift 2
            ;;
        -v|--revision)
            REVISION="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option $1"
            usage
            exit 1
            ;;
    esac
done

# Validate helm is installed
if ! command -v helm &> /dev/null; then
    print_error "Helm is not installed or not in PATH"
    exit 1
fi

# Validate kubectl is installed
if ! command -v kubectl &> /dev/null; then
    print_error "kubectl is not installed or not in PATH"
    exit 1
fi

# Check if release exists
print_status "Checking if release $RELEASE_NAME exists in namespace $NAMESPACE..."
if ! helm status "$RELEASE_NAME" -n "$NAMESPACE" &> /dev/null; then
    print_error "Release $RELEASE_NAME not found in namespace $NAMESPACE"
    exit 1
fi

# Get current revision
CURRENT_REVISION=$(helm history "$RELEASE_NAME" -n "$NAMESPACE" -o json | jq -r '.[-1].revision')
print_status "Current revision: $CURRENT_REVISION"

# Get available revisions
print_status "Available revisions:"
helm history "$RELEASE_NAME" -n "$NAMESPACE"

# Confirm rollback
if [[ "$REVISION" -eq 0 ]]; then
    print_warning "You are about to rollback to the previous version (revision $((CURRENT_REVISION - 1)))"
else
    print_warning "You are about to rollback to revision $REVISION"
fi

read -p "Do you want to continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Rollback cancelled"
    exit 0
fi

# Perform rollback
print_status "Performing rollback..."
if helm rollback "$RELEASE_NAME" "$REVISION" -n "$NAMESPACE"; then
    print_status "Rollback initiated successfully"
else
    print_error "Rollback failed"
    exit 1
fi

# Wait for rollout to complete
print_status "Waiting for rollout to complete..."
kubectl rollout status deployment/"$RELEASE_NAME" -n "$NAMESPACE" --timeout=300s

# Show final status
print_status "Rollback completed successfully!"
print_status "Current release status:"
helm status "$RELEASE_NAME" -n "$NAMESPACE"

# Show pod status
print_status "Pod status:"
kubectl get pods -n "$NAMESPACE" -l "app.kubernetes.io/instance=$RELEASE_NAME"

# Get service URL for health check
SERVICE_URL=$(kubectl get ingress "$RELEASE_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.rules[0].host}' 2>/dev/null || echo "")
if [[ -n "$SERVICE_URL" ]]; then
    print_status "Service URL: https://$SERVICE_URL"
    print_status "Performing health check..."
    if curl -f -s "https://$SERVICE_URL/api/v1/health" > /dev/null; then
        print_status "Health check passed!"
    else
        print_warning "Health check failed - please verify the deployment manually"
    fi
fi

print_status "Rollback process completed!"
