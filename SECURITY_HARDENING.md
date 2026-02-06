# Strands Security Hardening Guide

This document outlines security best practices and hardening measures for the Strands agent system in production environments.

## Table of Contents

1. [Application Security](#application-security)
2. [Infrastructure Security](#infrastructure-security)
3. [Data Security](#data-security)
4. [Access Control](#access-control)
5. [Monitoring & Incident Response](#monitoring--incident-response)
6. [Compliance](#compliance)

## Application Security

### Input Validation

**Requirement:** All user inputs must be validated and sanitized before processing.

**Implementation:**
- Use Pydantic models for request validation
- Implement input validation middleware (see `security_middleware.py`)
- Validate file uploads (size, type, content)
- Sanitize all user-provided strings

**Example:**
```python
from pydantic import BaseModel, Field, validator

class IncidentRequest(BaseModel):
    incident_id: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=5000)
    
    @validator('incident_id')
    def validate_incident_id(cls, v):
        if not v.isalnum():
            raise ValueError('Incident ID must be alphanumeric')
        return v
```

### Rate Limiting

**Requirement:** Protect APIs from abuse and DoS attacks.

**Implementation:**
- Implement per-IP rate limiting (60 requests/minute default)
- Use Redis for distributed rate limiting in multi-instance deployments
- Configure different limits for different endpoints
- Return 429 (Too Many Requests) when limit exceeded

**Configuration:**
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/api/incidents")
@limiter.limit("60/minute")
async def get_incidents(request: Request):
    pass
```

### Authentication & Authorization

**Requirement:** Secure API access with authentication and role-based authorization.

**Implementation:**
- Use JWT tokens for API authentication
- Implement OAuth 2.0 with authorization code flow
- Use short-lived access tokens (15 minutes) and refresh tokens (7 days)
- Implement role-based access control (RBAC)

**JWT Configuration:**
```python
from fastapi.security import HTTPBearer, HTTPAuthCredentials
from jose import JWTError, jwt

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthCredentials) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"]
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

### HTTPS/TLS

**Requirement:** All communications must be encrypted in transit.

**Implementation:**
- Use TLS 1.2+ for all connections
- Implement HSTS (HTTP Strict-Transport-Security)
- Use strong cipher suites
- Obtain certificates from trusted CAs

**Kubernetes Configuration:**
```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: strands-cert
spec:
  secretName: strands-tls
  issuerRef:
    name: letsencrypt-prod
  dnsNames:
  - strands.example.com
```

### Secrets Management

**Requirement:** Never hardcode secrets in code or configuration files.

**Implementation:**
- Use environment variables for secrets
- Use Kubernetes Secrets for sensitive data
- Rotate secrets regularly (every 90 days)
- Use HashiCorp Vault for centralized secret management
- Never commit secrets to version control

**Best Practices:**
```python
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    neo4j_password: str = os.getenv("NEO4J_PASSWORD")
    api_key: str = os.getenv("API_KEY")
    jwt_secret: str = os.getenv("JWT_SECRET")
    
    class Config:
        env_file = ".env"  # Only for development
```

### Dependency Management

**Requirement:** Keep dependencies up-to-date and free of known vulnerabilities.

**Implementation:**
- Use `pip-audit` or `safety` to scan for vulnerabilities
- Update dependencies regularly
- Use pinned versions in production
- Implement automated dependency scanning in CI/CD

**CI/CD Integration:**
```yaml
- name: Security Scan Dependencies
  run: |
    pip install safety
    safety check --json > safety-report.json
```

## Infrastructure Security

### Kubernetes Security

**Pod Security Standards:**
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: strands-api
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
  containers:
  - name: api
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop:
        - ALL
```

**Network Policies:**
- Implement network policies to restrict traffic
- Use ingress policies to allow only necessary traffic
- Implement egress policies to prevent data exfiltration
- Use service mesh (Istio) for advanced traffic management

**RBAC Configuration:**
- Create service accounts for each component
- Use least privilege principle
- Audit RBAC changes regularly
- Use ClusterRoles and ClusterRoleBindings appropriately

### Container Security

**Image Security:**
- Use minimal base images (Alpine, distroless)
- Scan images for vulnerabilities (Trivy, Grype)
- Sign images with Cosign
- Use private registries
- Implement image pull policies

**Runtime Security:**
- Use seccomp profiles
- Use AppArmor or SELinux
- Monitor container behavior
- Use runtime security tools (Falco)

### Network Security

**Firewall Rules:**
- Restrict inbound traffic to necessary ports
- Restrict outbound traffic to known destinations
- Use VPN for management access
- Implement DDoS protection

**DNS Security:**
- Use DNSSEC
- Implement DNS filtering
- Monitor DNS queries

## Data Security

### Encryption at Rest

**Requirement:** All sensitive data must be encrypted when stored.

**Implementation:**
- Enable encryption for database volumes
- Use encrypted backups
- Encrypt secrets in Kubernetes etcd
- Use application-level encryption for sensitive fields

**Kubernetes etcd Encryption:**
```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources:
  - secrets
  providers:
  - aescbc:
      keys:
      - name: key1
        secret: <base64-encoded-32-byte-key>
  - identity: {}
```

### Encryption in Transit

**Requirement:** All data in transit must be encrypted.

**Implementation:**
- Use TLS for all connections
- Use mTLS for service-to-service communication
- Encrypt database connections
- Use encrypted channels for API communication

### Data Classification

**Requirement:** Classify data by sensitivity level.

**Classification Levels:**
- **Public:** No restrictions
- **Internal:** Restricted to employees
- **Confidential:** Restricted to authorized personnel
- **Restricted:** Highly sensitive, maximum restrictions

### Data Retention & Deletion

**Requirement:** Implement data retention policies and secure deletion.

**Implementation:**
- Define retention periods for different data types
- Implement automated deletion of expired data
- Use secure deletion methods (overwrite, shredding)
- Document data lifecycle

## Access Control

### Authentication Methods

**Supported Methods:**
1. **API Keys:** For service-to-service communication
2. **JWT Tokens:** For user authentication
3. **OAuth 2.0:** For third-party integrations
4. **mTLS:** For Kubernetes service communication

### Authorization Levels

**Role Definitions:**
- **Admin:** Full access to all resources
- **Operator:** Can trigger incidents and view logs
- **Viewer:** Read-only access to incidents and metrics
- **Service:** Limited access for automated systems

### Audit Logging

**Requirement:** Log all access and changes for audit trail.

**Implementation:**
- Log all API calls with user, timestamp, action
- Log all configuration changes
- Log all authentication attempts
- Store audit logs securely and immutably
- Retain audit logs for at least 1 year

**Audit Log Format:**
```json
{
  "timestamp": "2024-01-20T10:30:00Z",
  "user": "user@example.com",
  "action": "GET /api/incidents",
  "resource": "/api/incidents",
  "status": 200,
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0..."
}
```

## Monitoring & Incident Response

### Security Monitoring

**Metrics to Monitor:**
- Failed authentication attempts
- Unusual API access patterns
- Rate limit violations
- Security policy violations
- Unauthorized access attempts

**Alerting Rules:**
```yaml
- alert: HighFailedAuthAttempts
  expr: rate(auth_failures_total[5m]) > 10
  for: 5m
  annotations:
    summary: "High rate of failed authentication"

- alert: UnusualAPIAccess
  expr: rate(api_requests_total[5m]) > 1000
  for: 5m
  annotations:
    summary: "Unusual API access pattern detected"
```

### Incident Response

**Incident Response Plan:**
1. **Detection:** Identify security incident
2. **Containment:** Isolate affected systems
3. **Investigation:** Determine scope and impact
4. **Remediation:** Fix the vulnerability
5. **Recovery:** Restore normal operations
6. **Post-Incident:** Review and improve

**Incident Response Team:**
- Security Lead
- Operations Lead
- Database Administrator
- Application Developer

### Vulnerability Management

**Vulnerability Scanning:**
- Scan code for vulnerabilities (SAST)
- Scan dependencies for vulnerabilities
- Scan containers for vulnerabilities
- Perform penetration testing quarterly

**Vulnerability Response:**
- Critical: Fix within 24 hours
- High: Fix within 7 days
- Medium: Fix within 30 days
- Low: Fix within 90 days

## Compliance

### Security Standards

**Compliance Requirements:**
- **OWASP Top 10:** Address all top 10 vulnerabilities
- **CIS Kubernetes Benchmarks:** Follow CIS recommendations
- **NIST Cybersecurity Framework:** Implement NIST guidelines
- **ISO 27001:** Information security management

### Security Testing

**Testing Requirements:**
- Unit tests for security functions
- Integration tests for authentication/authorization
- Penetration testing
- Security code review
- Dependency scanning

### Documentation

**Required Documentation:**
- Security architecture diagram
- Threat model
- Security policies
- Incident response plan
- Disaster recovery plan
- Security training materials

## Security Checklist

- [ ] All inputs validated and sanitized
- [ ] Rate limiting implemented
- [ ] Authentication and authorization configured
- [ ] HTTPS/TLS enabled
- [ ] Secrets managed securely
- [ ] Dependencies scanned for vulnerabilities
- [ ] Pod security standards enforced
- [ ] Network policies implemented
- [ ] RBAC configured
- [ ] Encryption at rest enabled
- [ ] Encryption in transit enabled
- [ ] Audit logging enabled
- [ ] Security monitoring configured
- [ ] Incident response plan documented
- [ ] Vulnerability scanning implemented
- [ ] Security testing completed
- [ ] Compliance requirements met
- [ ] Security training completed

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Kubernetes Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Kubernetes Security Best Practices](https://kubernetes.io/docs/concepts/security/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
