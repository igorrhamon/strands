# Strands Disaster Recovery Plan

This document outlines the disaster recovery procedures for the Strands agent system.

## Table of Contents

1. [Overview](#overview)
2. [Recovery Time Objectives](#recovery-time-objectives)
3. [Backup Strategy](#backup-strategy)
4. [Disaster Scenarios](#disaster-scenarios)
5. [Recovery Procedures](#recovery-procedures)
6. [Testing & Validation](#testing--validation)
7. [Contact & Escalation](#contact--escalation)

## Overview

The Strands Disaster Recovery Plan ensures business continuity and data protection in case of system failures, data loss, or catastrophic events.

**Key Components:**
- Neo4j graph database (incident data, relationships)
- Qdrant vector database (embeddings, semantic search)
- Strands API service (orchestration, agents)
- Configuration and secrets
- Logs and audit trails

## Recovery Time Objectives

| Component | RTO | RPO | Priority |
|-----------|-----|-----|----------|
| Neo4j Database | 1 hour | 15 minutes | Critical |
| Qdrant Database | 2 hours | 1 hour | High |
| Strands API | 30 minutes | 5 minutes | Critical |
| Configuration | 30 minutes | 0 minutes | Critical |
| Logs | 24 hours | 1 hour | Medium |

**Definitions:**
- **RTO (Recovery Time Objective):** Maximum acceptable downtime
- **RPO (Recovery Point Objective):** Maximum acceptable data loss

## Backup Strategy

### Backup Schedule

```
Daily Backups:
- Full backup at 2:00 AM UTC
- Incremental backups every 6 hours
- Retention: 30 days

Weekly Backups:
- Full backup every Sunday at 3:00 AM UTC
- Retention: 90 days

Monthly Backups:
- Full backup on the 1st of each month
- Retention: 1 year (stored offline)
```

### Backup Components

**1. Neo4j Database**
- Full database dump using `neo4j-admin database dump`
- Compressed with gzip
- Stored in backup location with encryption

**2. Qdrant Vector Database**
- Storage directory backup using tar
- Includes all collections and indexes
- Compressed with gzip

**3. Configuration**
- Kubernetes ConfigMaps
- Kubernetes Secrets (encrypted)
- RBAC policies
- Stored in YAML format

**4. Logs**
- Pod logs from all Strands components
- Stored in text format
- Compressed with gzip

### Backup Execution

**Manual Backup:**
```bash
./scripts/backup.sh /backups/strands 30
```

**Automated Backup (CronJob):**
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: strands-backup
  namespace: strands
spec:
  schedule: "0 2 * * *"  # 2 AM daily
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: strands-backup
          containers:
          - name: backup
            image: strands:latest
            command: ["/scripts/backup.sh", "/backups/strands", "30"]
          restartPolicy: OnFailure
```

### Backup Verification

Backups are verified automatically:
- Tar file integrity check
- Manifest file validation
- Backup size verification
- Timestamp validation

## Disaster Scenarios

### Scenario 1: Single Pod Failure

**Symptoms:**
- API pod crashes
- Service becomes unavailable
- Kubernetes automatically restarts pod

**Recovery Steps:**
1. Monitor pod restart (automatic)
2. Verify pod health: `kubectl get pods -n strands`
3. Check logs: `kubectl logs -n strands pod-name`
4. If pod doesn't recover, delete and recreate:
   ```bash
   kubectl delete pod -n strands strands-api-0
   ```

**RTO:** 5-10 minutes

### Scenario 2: Database Corruption

**Symptoms:**
- Database queries fail
- Errors in logs: "corrupted data"
- API returns 500 errors

**Recovery Steps:**
1. Stop Strands API:
   ```bash
   kubectl scale deployment strands-api --replicas=0 -n strands
   ```
2. Restore from backup:
   ```bash
   ./scripts/restore.sh /backups/strands/strands_backup_20240120_100000 strands
   ```
3. Verify restore:
   ```bash
   kubectl exec -n strands neo4j-0 -- cypher-shell -u neo4j "RETURN 1"
   ```
4. Restart Strands API:
   ```bash
   kubectl scale deployment strands-api --replicas=3 -n strands
   ```

**RTO:** 1 hour

### Scenario 3: Data Loss

**Symptoms:**
- Accidental deletion of data
- Data inconsistency
- Missing incident records

**Recovery Steps:**
1. Identify affected data
2. Restore from most recent backup
3. Verify data integrity
4. Reconcile with any external systems

**RTO:** 2 hours

### Scenario 4: Complete Cluster Failure

**Symptoms:**
- All pods down
- Cluster nodes unavailable
- Persistent volumes inaccessible

**Recovery Steps:**
1. Provision new Kubernetes cluster
2. Deploy Strands infrastructure:
   ```bash
   kubectl apply -f k8s/
   helm install strands ./helm/strands/
   ```
3. Restore databases from backup
4. Verify all services are running
5. Run smoke tests

**RTO:** 4 hours

### Scenario 5: Security Breach

**Symptoms:**
- Unauthorized access detected
- Data exfiltration suspected
- Malicious activity in logs

**Recovery Steps:**
1. Isolate affected systems
2. Preserve evidence (logs, snapshots)
3. Rotate all secrets:
   ```bash
   kubectl delete secret strands-secrets -n strands
   kubectl create secret generic strands-secrets \
     --from-literal=neo4j_password=<new-password> \
     -n strands
   ```
4. Restore from clean backup
5. Conduct security audit
6. Implement security fixes

**RTO:** 2-4 hours

## Recovery Procedures

### Restore from Backup

**Prerequisites:**
- Backup file exists and is accessible
- kubectl is configured and authenticated
- Target namespace exists

**Procedure:**
```bash
# 1. Verify backup integrity
ls -la /backups/strands/strands_backup_20240120_100000/

# 2. Execute restore script
./scripts/restore.sh /backups/strands/strands_backup_20240120_100000 strands

# 3. Verify restore
kubectl get pods -n strands
kubectl exec -n strands neo4j-0 -- cypher-shell -u neo4j "RETURN 1"

# 4. Run smoke tests
kubectl exec -n strands strands-api-0 -- curl http://localhost:8000/health
```

### Manual Database Recovery

**Neo4j Recovery:**
```bash
# 1. Connect to Neo4j pod
kubectl exec -it -n strands neo4j-0 -- bash

# 2. Stop Neo4j
neo4j stop

# 3. Restore database
neo4j-admin database load neo4j \
  --from-path=/var/lib/neo4j/backups/ \
  --verbose

# 4. Start Neo4j
neo4j start

# 5. Verify
cypher-shell -u neo4j -p <password> "RETURN 1"
```

**Qdrant Recovery:**
```bash
# 1. Connect to Qdrant pod
kubectl exec -it -n strands qdrant-0 -- bash

# 2. Stop Qdrant
kill $(pgrep qdrant)

# 3. Restore storage
tar -xzf /backups/qdrant.tar.gz -C /qdrant/

# 4. Start Qdrant
/qdrant/qdrant

# 5. Verify
curl http://localhost:6333/health
```

### Failover to Secondary

**For multi-region deployments:**

```bash
# 1. Verify secondary cluster is healthy
kubectl cluster-info

# 2. Update DNS to point to secondary
# (Update DNS records to secondary cluster IP)

# 3. Restore data to secondary
./scripts/restore.sh /backups/strands/latest strands

# 4. Verify secondary is operational
kubectl get pods -n strands
kubectl get svc -n strands

# 5. Monitor traffic migration
# (Monitor logs and metrics during traffic shift)
```

## Testing & Validation

### Backup Testing

**Monthly Backup Test:**
```bash
# 1. Create test environment
kubectl create namespace strands-test

# 2. Restore backup to test environment
./scripts/restore.sh /backups/strands/latest strands-test

# 3. Run validation tests
kubectl exec -n strands-test strands-api-0 -- \
  pytest tests/integration/test_recovery.py

# 4. Cleanup
kubectl delete namespace strands-test
```

### Recovery Testing

**Quarterly Disaster Recovery Drill:**
1. Schedule DR drill (off-peak hours)
2. Simulate failure scenario
3. Execute recovery procedure
4. Measure RTO and RPO
5. Document results
6. Update procedures based on findings

### Smoke Tests

**Post-Recovery Validation:**
```bash
#!/bin/bash

echo "Running smoke tests..."

# Test API health
curl -f http://strands-api:8000/health || exit 1

# Test Neo4j connectivity
kubectl exec -n strands neo4j-0 -- \
  cypher-shell -u neo4j "RETURN 1" || exit 1

# Test Qdrant connectivity
kubectl exec -n strands qdrant-0 -- \
  curl -f http://localhost:6333/health || exit 1

# Test incident retrieval
curl -f http://strands-api:8000/api/incidents || exit 1

echo "All smoke tests passed!"
```

## Contact & Escalation

### Incident Response Team

| Role | Name | Contact | Backup |
|------|------|---------|--------|
| Incident Commander | [Name] | [Email] | [Backup] |
| Database Admin | [Name] | [Email] | [Backup] |
| Infrastructure Lead | [Name] | [Email] | [Backup] |
| Security Lead | [Name] | [Email] | [Backup] |

### Escalation Path

1. **Level 1 (0-15 min):** On-call engineer
2. **Level 2 (15-30 min):** Team lead
3. **Level 3 (30-60 min):** Manager
4. **Level 4 (60+ min):** Director

### Communication

**During Incident:**
- Slack channel: #strands-incident
- Status page: https://status.example.com
- Customer notification: [Process]

**Post-Incident:**
- Incident report: Within 24 hours
- Root cause analysis: Within 48 hours
- Action items: Within 1 week

## Appendix

### Backup Manifest Format

```json
{
  "backup_name": "strands_backup_20240120_100000",
  "timestamp": "2024-01-20T10:00:00Z",
  "backup_dir": "/backups/strands/strands_backup_20240120_100000",
  "retention_days": 30,
  "components": {
    "neo4j": "neo4j.tar.gz",
    "qdrant": "qdrant.tar.gz",
    "config": "config.tar.gz",
    "logs": "logs.tar.gz"
  },
  "kubernetes": {
    "namespace": "strands",
    "cluster": "prod-cluster"
  },
  "size_bytes": 1073741824
}
```

### Useful Commands

```bash
# List all backups
ls -la /backups/strands/

# Check backup size
du -sh /backups/strands/strands_backup_*

# Verify backup integrity
tar -tzf /backups/strands/strands_backup_*/neo4j.tar.gz | head

# Get backup manifest
cat /backups/strands/strands_backup_*/MANIFEST.json | jq .

# Monitor restore progress
kubectl logs -n strands -f job/strands-restore

# Check database size
kubectl exec -n strands neo4j-0 -- \
  cypher-shell -u neo4j "CALL dbms.queryJmx('java.lang:type=Memory') YIELD attributes RETURN attributes"
```

## References

- [Neo4j Backup and Restore](https://neo4j.com/docs/operations-manual/current/backup-restore/)
- [Qdrant Backup](https://qdrant.tech/documentation/concepts/backup/)
- [Kubernetes Backup Best Practices](https://kubernetes.io/docs/tasks/administer-cluster/configure-upgrade-api/)
- [Disaster Recovery Planning](https://en.wikipedia.org/wiki/Disaster_recovery)
