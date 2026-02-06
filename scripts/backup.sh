#!/bin/bash

################################################################################
# Strands Backup Script
#
# This script performs backup of all critical Strands components:
# - Neo4j database
# - Qdrant vector database
# - Configuration files
# - Logs
#
# Usage: ./backup.sh [backup_dir] [retention_days]
# Example: ./backup.sh /backups/strands 30
################################################################################

set -euo pipefail

# Configuration
BACKUP_DIR="${1:-.backup}"
RETENTION_DAYS="${2:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="strands_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Kubernetes configuration
NAMESPACE="strands"
NEO4J_POD="neo4j-0"
QDRANT_POD="qdrant-0"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create backup directory
mkdir -p "${BACKUP_PATH}"
log_info "Created backup directory: ${BACKUP_PATH}"

# Backup Neo4j
backup_neo4j() {
    log_info "Starting Neo4j backup..."
    
    NEO4J_BACKUP_DIR="${BACKUP_PATH}/neo4j"
    mkdir -p "${NEO4J_BACKUP_DIR}"
    
    # Execute backup command in Neo4j pod
    kubectl exec -n "${NAMESPACE}" "${NEO4J_POD}" -- \
        neo4j-admin database dump neo4j \
        --to-path=/var/lib/neo4j/backups/ \
        --verbose || {
        log_error "Neo4j backup failed"
        return 1
    }
    
    # Copy backup from pod
    kubectl cp "${NAMESPACE}/${NEO4J_POD}:/var/lib/neo4j/backups/" \
        "${NEO4J_BACKUP_DIR}/" || {
        log_error "Failed to copy Neo4j backup from pod"
        return 1
    }
    
    # Compress backup
    tar -czf "${NEO4J_BACKUP_DIR}.tar.gz" -C "${BACKUP_PATH}" neo4j
    rm -rf "${NEO4J_BACKUP_DIR}"
    
    log_info "Neo4j backup completed: ${NEO4J_BACKUP_DIR}.tar.gz"
}

# Backup Qdrant
backup_qdrant() {
    log_info "Starting Qdrant backup..."
    
    QDRANT_BACKUP_DIR="${BACKUP_PATH}/qdrant"
    mkdir -p "${QDRANT_BACKUP_DIR}"
    
    # Get Qdrant data directory
    kubectl exec -n "${NAMESPACE}" "${QDRANT_POD}" -- \
        tar -czf - /qdrant/storage/ | tar -xzf - -C "${QDRANT_BACKUP_DIR}" || {
        log_error "Qdrant backup failed"
        return 1
    }
    
    # Compress backup
    tar -czf "${QDRANT_BACKUP_DIR}.tar.gz" -C "${BACKUP_PATH}" qdrant
    rm -rf "${QDRANT_BACKUP_DIR}"
    
    log_info "Qdrant backup completed: ${QDRANT_BACKUP_DIR}.tar.gz"
}

# Backup configuration
backup_config() {
    log_info "Starting configuration backup..."
    
    CONFIG_BACKUP_DIR="${BACKUP_PATH}/config"
    mkdir -p "${CONFIG_BACKUP_DIR}"
    
    # Backup ConfigMaps
    kubectl get configmap -n "${NAMESPACE}" -o yaml > \
        "${CONFIG_BACKUP_DIR}/configmaps.yaml" || {
        log_error "Failed to backup ConfigMaps"
        return 1
    }
    
    # Backup Secrets (encrypted)
    kubectl get secret -n "${NAMESPACE}" -o yaml > \
        "${CONFIG_BACKUP_DIR}/secrets.yaml" || {
        log_error "Failed to backup Secrets"
        return 1
    }
    
    # Backup RBAC
    kubectl get rolebinding -n "${NAMESPACE}" -o yaml > \
        "${CONFIG_BACKUP_DIR}/rolebindings.yaml" || {
        log_error "Failed to backup RoleBindings"
        return 1
    }
    
    # Compress backup
    tar -czf "${CONFIG_BACKUP_DIR}.tar.gz" -C "${BACKUP_PATH}" config
    rm -rf "${CONFIG_BACKUP_DIR}"
    
    log_info "Configuration backup completed: ${CONFIG_BACKUP_DIR}.tar.gz"
}

# Backup logs
backup_logs() {
    log_info "Starting logs backup..."
    
    LOGS_BACKUP_DIR="${BACKUP_PATH}/logs"
    mkdir -p "${LOGS_BACKUP_DIR}"
    
    # Get logs from all Strands pods
    for pod in $(kubectl get pods -n "${NAMESPACE}" -l app=strands -o jsonpath='{.items[*].metadata.name}'); do
        log_info "Collecting logs from pod: ${pod}"
        kubectl logs -n "${NAMESPACE}" "${pod}" > "${LOGS_BACKUP_DIR}/${pod}.log" || {
            log_warn "Failed to get logs from ${pod}"
        }
    done
    
    # Compress backup
    tar -czf "${LOGS_BACKUP_DIR}.tar.gz" -C "${BACKUP_PATH}" logs
    rm -rf "${LOGS_BACKUP_DIR}"
    
    log_info "Logs backup completed: ${LOGS_BACKUP_DIR}.tar.gz"
}

# Create backup manifest
create_manifest() {
    log_info "Creating backup manifest..."
    
    MANIFEST="${BACKUP_PATH}/MANIFEST.json"
    
    cat > "${MANIFEST}" << EOF
{
  "backup_name": "${BACKUP_NAME}",
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "backup_dir": "${BACKUP_PATH}",
  "retention_days": ${RETENTION_DAYS},
  "components": {
    "neo4j": "neo4j.tar.gz",
    "qdrant": "qdrant.tar.gz",
    "config": "config.tar.gz",
    "logs": "logs.tar.gz"
  },
  "kubernetes": {
    "namespace": "${NAMESPACE}",
    "cluster": "$(kubectl config current-context)"
  },
  "size_bytes": $(du -sb "${BACKUP_PATH}" | cut -f1)
}
EOF
    
    log_info "Backup manifest created: ${MANIFEST}"
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up backups older than ${RETENTION_DAYS} days..."
    
    find "${BACKUP_DIR}" -maxdepth 1 -type d -name "strands_backup_*" \
        -mtime "+${RETENTION_DAYS}" -exec rm -rf {} \; || {
        log_warn "Failed to cleanup some old backups"
    }
    
    log_info "Cleanup completed"
}

# Verify backup
verify_backup() {
    log_info "Verifying backup integrity..."
    
    # Check if all expected files exist
    local files=("neo4j.tar.gz" "qdrant.tar.gz" "config.tar.gz" "logs.tar.gz" "MANIFEST.json")
    
    for file in "${files[@]}"; do
        if [ ! -f "${BACKUP_PATH}/${file}" ]; then
            log_error "Missing backup file: ${file}"
            return 1
        fi
    done
    
    # Verify tar files
    for tar_file in "${BACKUP_PATH}"/*.tar.gz; do
        if ! tar -tzf "${tar_file}" > /dev/null 2>&1; then
            log_error "Corrupted tar file: ${tar_file}"
            return 1
        fi
    done
    
    log_info "Backup verification completed successfully"
}

# Main execution
main() {
    log_info "Starting Strands backup process..."
    log_info "Backup directory: ${BACKUP_DIR}"
    log_info "Retention period: ${RETENTION_DAYS} days"
    
    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed or not in PATH"
        exit 1
    fi
    
    # Perform backups
    backup_neo4j || exit 1
    backup_qdrant || exit 1
    backup_config || exit 1
    backup_logs || exit 1
    
    # Create manifest
    create_manifest
    
    # Verify backup
    verify_backup || exit 1
    
    # Cleanup old backups
    cleanup_old_backups
    
    log_info "Backup completed successfully!"
    log_info "Backup location: ${BACKUP_PATH}"
    log_info "Backup size: $(du -sh "${BACKUP_PATH}" | cut -f1)"
}

# Run main function
main "$@"
