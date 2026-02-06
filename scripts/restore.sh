#!/bin/bash

################################################################################
# Strands Restore Script
#
# This script restores Strands from a backup created by backup.sh
#
# Usage: ./restore.sh <backup_path> [namespace]
# Example: ./restore.sh /backups/strands/strands_backup_20240120_100000 strands
################################################################################

set -euo pipefail

# Configuration
BACKUP_PATH="${1:-.}"
NAMESPACE="${2:-strands}"
RESTORE_LOG="${BACKUP_PATH}/restore_$(date +%Y%m%d_%H%M%S).log"

# Kubernetes configuration
NEO4J_POD="neo4j-0"
QDRANT_POD="qdrant-0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1" | tee -a "${RESTORE_LOG}"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" | tee -a "${RESTORE_LOG}"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "${RESTORE_LOG}"
}

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1" | tee -a "${RESTORE_LOG}"
}

# Verify backup integrity
verify_backup() {
    log_info "Verifying backup integrity..."
    
    if [ ! -f "${BACKUP_PATH}/MANIFEST.json" ]; then
        log_error "Backup manifest not found: ${BACKUP_PATH}/MANIFEST.json"
        return 1
    fi
    
    # Check if all expected files exist
    local files=("neo4j.tar.gz" "qdrant.tar.gz" "config.tar.gz" "logs.tar.gz")
    
    for file in "${files[@]}"; do
        if [ ! -f "${BACKUP_PATH}/${file}" ]; then
            log_warn "Optional backup file missing: ${file}"
        fi
    done
    
    log_info "Backup verification completed"
}

# Restore Neo4j
restore_neo4j() {
    log_info "Starting Neo4j restore..."
    
    if [ ! -f "${BACKUP_PATH}/neo4j.tar.gz" ]; then
        log_warn "Neo4j backup not found, skipping restore"
        return 0
    fi
    
    # Create temporary directory
    local temp_dir=$(mktemp -d)
    trap "rm -rf ${temp_dir}" EXIT
    
    # Extract backup
    tar -xzf "${BACKUP_PATH}/neo4j.tar.gz" -C "${temp_dir}"
    
    # Copy backup to pod
    kubectl cp "${temp_dir}/neo4j/" \
        "${NAMESPACE}/${NEO4J_POD}:/var/lib/neo4j/backups/" || {
        log_error "Failed to copy Neo4j backup to pod"
        return 1
    }
    
    # Execute restore command in Neo4j pod
    kubectl exec -n "${NAMESPACE}" "${NEO4J_POD}" -- \
        neo4j-admin database load neo4j \
        --from-path=/var/lib/neo4j/backups/ \
        --verbose || {
        log_error "Neo4j restore failed"
        return 1
    }
    
    log_info "Neo4j restore completed"
}

# Restore Qdrant
restore_qdrant() {
    log_info "Starting Qdrant restore..."
    
    if [ ! -f "${BACKUP_PATH}/qdrant.tar.gz" ]; then
        log_warn "Qdrant backup not found, skipping restore"
        return 0
    fi
    
    # Create temporary directory
    local temp_dir=$(mktemp -d)
    trap "rm -rf ${temp_dir}" EXIT
    
    # Extract backup
    tar -xzf "${BACKUP_PATH}/qdrant.tar.gz" -C "${temp_dir}"
    
    # Stop Qdrant pod
    log_info "Stopping Qdrant pod..."
    kubectl delete pod -n "${NAMESPACE}" "${QDRANT_POD}" --wait=true || {
        log_warn "Failed to stop Qdrant pod, continuing anyway"
    }
    
    # Wait for pod to be deleted
    sleep 5
    
    # Copy backup to pod (pod will be recreated)
    log_info "Waiting for Qdrant pod to be recreated..."
    kubectl wait --for=condition=ready pod \
        -l statefulset.kubernetes.io/pod-name="${QDRANT_POD}" \
        -n "${NAMESPACE}" --timeout=300s || {
        log_error "Qdrant pod did not start in time"
        return 1
    }
    
    # Copy backup data
    kubectl cp "${temp_dir}/qdrant/qdrant/storage/" \
        "${NAMESPACE}/${QDRANT_POD}:/qdrant/storage/" || {
        log_error "Failed to copy Qdrant backup to pod"
        return 1
    }
    
    log_info "Qdrant restore completed"
}

# Restore configuration
restore_config() {
    log_info "Starting configuration restore..."
    
    if [ ! -f "${BACKUP_PATH}/config.tar.gz" ]; then
        log_warn "Configuration backup not found, skipping restore"
        return 0
    fi
    
    # Create temporary directory
    local temp_dir=$(mktemp -d)
    trap "rm -rf ${temp_dir}" EXIT
    
    # Extract backup
    tar -xzf "${BACKUP_PATH}/config.tar.gz" -C "${temp_dir}"
    
    # Restore ConfigMaps
    log_info "Restoring ConfigMaps..."
    kubectl apply -f "${temp_dir}/config/configmaps.yaml" || {
        log_warn "Failed to restore some ConfigMaps"
    }
    
    # Restore Secrets
    log_info "Restoring Secrets..."
    kubectl apply -f "${temp_dir}/config/secrets.yaml" || {
        log_warn "Failed to restore some Secrets"
    }
    
    # Restore RoleBindings
    log_info "Restoring RoleBindings..."
    kubectl apply -f "${temp_dir}/config/rolebindings.yaml" || {
        log_warn "Failed to restore some RoleBindings"
    }
    
    log_info "Configuration restore completed"
}

# Verify restore
verify_restore() {
    log_info "Verifying restore..."
    
    # Check Neo4j
    log_info "Checking Neo4j..."
    kubectl exec -n "${NAMESPACE}" "${NEO4J_POD}" -- \
        cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
        "RETURN 1" > /dev/null 2>&1 || {
        log_warn "Neo4j verification failed"
    }
    
    # Check Qdrant
    log_info "Checking Qdrant..."
    kubectl exec -n "${NAMESPACE}" "${QDRANT_POD}" -- \
        curl -s http://localhost:6333/health > /dev/null || {
        log_warn "Qdrant verification failed"
    }
    
    # Check API
    log_info "Checking Strands API..."
    kubectl exec -n "${NAMESPACE}" -l app=strands,component=api -c api -- \
        curl -s http://localhost:8000/health > /dev/null || {
        log_warn "Strands API verification failed"
    }
    
    log_info "Restore verification completed"
}

# Create restore report
create_report() {
    log_info "Creating restore report..."
    
    local report="${BACKUP_PATH}/restore_report_$(date +%Y%m%d_%H%M%S).json"
    
    cat > "${report}" << EOF
{
  "restore_timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "backup_path": "${BACKUP_PATH}",
  "namespace": "${NAMESPACE}",
  "restore_log": "${RESTORE_LOG}",
  "status": "completed"
}
EOF
    
    log_info "Restore report created: ${report}"
}

# Main execution
main() {
    log_info "Starting Strands restore process..."
    log_info "Backup path: ${BACKUP_PATH}"
    log_info "Target namespace: ${NAMESPACE}"
    log_info "Restore log: ${RESTORE_LOG}"
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Check if backup path exists
    if [ ! -d "${BACKUP_PATH}" ]; then
        log_error "Backup path does not exist: ${BACKUP_PATH}"
        exit 1
    fi
    
    # Verify backup
    verify_backup || exit 1
    
    # Prompt for confirmation
    echo ""
    echo -e "${YELLOW}WARNING: This will restore Strands from backup!${NC}"
    echo "Backup path: ${BACKUP_PATH}"
    echo "Target namespace: ${NAMESPACE}"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        log_info "Restore cancelled by user"
        exit 0
    fi
    
    # Perform restore
    restore_neo4j || exit 1
    restore_qdrant || exit 1
    restore_config || exit 1
    
    # Verify restore
    verify_restore
    
    # Create report
    create_report
    
    log_info "Restore completed successfully!"
}

# Run main function
main "$@"
