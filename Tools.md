# Tools - Tools and Integrations

## Overview

This document describes all external tools and systems that our PKI agents interact with. These are the trusted components that perform actual cryptographic operations—the AI agents orchestrate these tools but never perform crypto themselves.

**Remember**: AI plans, tools execute.

---

## Tool Categories

```
┌─────────────────────────────────────────────────┐
│              AI Layer (Planning)                │
│  Orchestrator + Specialized Agents              │
└────────┬────────────────────────────────────────┘
         │
         │ Calls tools (never does crypto)
         │
    ┌────┴────┬──────────┬──────────┬─────────┐
    │         │          │          │         │
    ▼         ▼          ▼          ▼         ▼
┌────────┐ ┌──────┐ ┌────────┐ ┌──────┐ ┌──────┐
│Vault/  │ │OpenSSL│ │CA APIs │ │Database│ │Logs │
│HSM     │ │       │ │        │ │      │ │     │
└────────┘ └──────┘ └────────┘ └──────┘ └──────┘
```

---

## 1. Key Management: HashiCorp Vault

### What It Does

Vault is our primary key management system. It generates, stores, and manages cryptographic keys in a hardware security module (HSM) or software backend.

### Why We Use It

- **Keys never leave Vault**: Private keys stay in HSM, only references are shared
- **FIPS 140-2 compliant**: Meets regulatory requirements
- **Audit logging**: Every key operation is logged
- **Access control**: Fine-grained permissions via policies

### Integration Points

#### 1. Transit Engine (Key Generation)

**Purpose**: Generate asymmetric key pairs

**Agent**: Key Management Agent

**API Call**:
```bash
# Create RSA 4096 key
POST /v1/transit/keys/my-key
{
  "type": "rsa-4096",
  "exportable": false
}

Response:
{
  "data": {
    "name": "my-key",
    "type": "rsa-4096",
    "latest_version": 1
  }
}
```

**What We Get Back**: Key reference (`transit/keys/my-key`), NOT the actual key

#### 2. Public Key Retrieval

**Purpose**: Get public key for CSR creation

**API Call**:
```bash
GET /v1/transit/keys/my-key

Response:
{
  "data": {
    "keys": {
      "1": {
        "public_key": "-----BEGIN PUBLIC KEY-----\n..."
      }
    }
  }
}
```

#### 3. Key Rotation

**Purpose**: Rotate key without changing reference

**API Call**:
```bash
POST /v1/transit/keys/my-key/rotate
```

New version created, old version still accessible for decryption of old data.

#### 4. Key Deletion

**Purpose**: Destroy key material (e.g., after revocation for key compromise)

**API Call**:
```bash
DELETE /v1/transit/keys/my-key
{
  "deletion_allowed": true
}
```

### Configuration

```hcl
# vault-config.hcl
path "transit/keys/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "transit/keys/+/rotate" {
  capabilities = ["update"]
}

# Deny export of private keys
path "transit/export/*" {
  capabilities = ["deny"]
}
```

### Alternatives

- **AWS KMS**: Cloud-native, integrates with AWS services
- **Azure Key Vault**: Microsoft cloud alternative
- **Google Cloud KMS**: GCP alternative
- **YubiHSM**: Hardware HSM for on-premise

**Why Vault?** Multi-cloud support, open source option, excellent API, widely adopted.

---

## 2. Certificate Operations: OpenSSL

### What It Does

OpenSSL is the industry-standard toolkit for SSL/TLS and cryptographic operations. We use it for CSR creation and certificate validation.

### Why We Use It

- **Battle-tested**: Used everywhere, thoroughly audited
- **Standard compliance**: Implements X.509, PKCS standards
- **Flexible**: Supports all algorithms and formats
- **Free and open source**

### Integration Points

#### 1. CSR Generation

**Purpose**: Create Certificate Signing Request

**Agent**: Certificate Agent

**Command**:
```bash
openssl req -new \
  -key public_key.pem \
  -config csr.conf \
  -out request.csr
```

**Config File** (`csr.conf`):
```ini
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
CN = api.example.com
O = Example Corp
OU = Engineering
C = US

[v3_req]
subjectAltName = @alt_names
keyUsage = digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth

[alt_names]
DNS.1 = api.example.com
DNS.2 = www.example.com
```

**Output**: CSR in PEM format
```
-----BEGIN CERTIFICATE REQUEST-----
MIICvDCCAaQCAQAwdzELMAkGA1UEBhMCVVMxEzARBgNVBAgMCkNhbGlmb3JuaWEx
...
-----END CERTIFICATE REQUEST-----
```

#### 2. CSR Validation

**Purpose**: Verify CSR is well-formed

**Command**:
```bash
openssl req -in request.csr -noout -text

Output:
Certificate Request:
    Data:
        Version: 1 (0x0)
        Subject: CN=api.example.com, O=Example Corp...
        Subject Public Key Info:
            Public Key Algorithm: rsaEncryption
                RSA Public-Key: (4096 bit)
```

#### 3. Certificate Validation

**Purpose**: Verify certificate chain and validity

**Command**:
```bash
# Verify certificate against CA
openssl verify -CAfile ca-cert.pem certificate.pem

# Check certificate details
openssl x509 -in certificate.pem -noout -text
```

#### 4. Certificate Chain Building

**Purpose**: Construct full certificate chain

**Command**:
```bash
cat certificate.pem intermediate-ca.pem root-ca.pem > full-chain.pem
```

### Python Integration

```python
import subprocess

def create_csr(subject, public_key, sans):
    # Write config
    config = generate_openssl_config(subject, sans)
    with open('/tmp/csr.conf', 'w') as f:
        f.write(config)
    
    # Write public key
    with open('/tmp/public_key.pem', 'w') as f:
        f.write(public_key)
    
    # Generate CSR
    result = subprocess.run([
        'openssl', 'req', '-new',
        '-key', '/tmp/public_key.pem',
        '-config', '/tmp/csr.conf',
        '-out', '/tmp/request.csr'
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        raise Exception(f"CSR creation failed: {result.stderr}")
    
    # Read CSR
    with open('/tmp/request.csr', 'r') as f:
        return f.read()
```

### Alternatives

- **cfssl**: CloudFlare's PKI toolkit (Go-based)
- **certbot**: Let's Encrypt client (ACME protocol)
- **LibreSSL**: OpenBSD fork of OpenSSL

**Why OpenSSL?** Universal compatibility, comprehensive features, industry standard.

---

## 3. Certificate Authority: Multiple Options

### Option A: Internal CA (EJBCA)

**What It Does**: Enterprise-grade certificate authority software

**Use Case**: Internal certificates, full control

**Integration**:
```python
import requests

def issue_certificate(csr, validity_days):
    response = requests.post(
        "https://ca.internal/ejbca/ejbca-rest-api/v1/certificate/certificaterequest",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        },
        json={
            "certificate_request": csr,
            "certificate_profile_name": "TLS_SERVER",
            "end_entity_profile_name": "WebServer",
            "validity": f"{validity_days}d"
        }
    )
    
    return response.json()['certificate']
```

**Pros**: Full control, customizable policies, air-gapped option
**Cons**: Requires infrastructure, maintenance

### Option B: Let's Encrypt (ACME Protocol)

**What It Does**: Free, automated certificate authority

**Use Case**: Public-facing web servers, domain-validated certs

**Integration**:
```python
from acme import client, messages
from cryptography.hazmat.primitives import serialization

def issue_certificate_acme(domain, csr):
    # Create ACME client
    acme_client = client.ClientV2(
        net=client.ClientNetwork(key),
        directory=messages.Directory.from_json(acme_directory)
    )
    
    # Request certificate
    order = acme_client.new_order(csr)
    
    # Handle challenges (DNS or HTTP)
    for authz in order.authorizations:
        challenge = authz.body.challenges[0]  # DNS-01 or HTTP-01
        acme_client.answer_challenge(challenge, challenge.response(key))
    
    # Finalize order
    order = acme_client.poll_and_finalize(order)
    
    return order.fullchain_pem
```

**Pros**: Free, automated, trusted by browsers
**Cons**: Domain validation only, 90-day max validity, rate limits

### Option C: AWS Certificate Manager

**What It Does**: Managed certificate service for AWS resources

**Use Case**: AWS-hosted applications, load balancers

**Integration**:
```python
import boto3

acm = boto3.client('acm')

def request_certificate(domain):
    response = acm.request_certificate(
        DomainName=domain,
        ValidationMethod='DNS',
        SubjectAlternativeNames=[domain, f"*.{domain}"]
    )
    
    return response['CertificateArn']
```

**Pros**: Fully managed, auto-renewal, free for AWS resources
**Cons**: Locked to AWS, can't export private keys

### Option D: Cloud CA Services

- **DigiCert**: Public CA, OV/EV certificates
- **GlobalSign**: Public CA, various validation levels
- **Sectigo**: Public CA, affordable options

**Integration**: REST APIs similar to EJBCA example

### Our Approach

**Hybrid model**:
- **Internal services**: EJBCA (full control)
- **Public web**: Let's Encrypt (free, automated)
- **AWS resources**: ACM (managed)

Certificate Agent abstracts the CA backend:
```python
def issue_certificate(csr, ca_type):
    if ca_type == "internal":
        return ejbca_issue(csr)
    elif ca_type == "letsencrypt":
        return acme_issue(csr)
    elif ca_type == "aws":
        return acm_issue(csr)
```

---

## 4. Database: PostgreSQL

### What It Does

Stores certificate inventory, metadata, and lifecycle state.

### Why PostgreSQL?

- **ACID compliance**: Data integrity guaranteed
- **JSON support**: Flexible schema for metadata
- **Full-text search**: Find certificates by subject, SAN
- **Partitioning**: Handle millions of certificates
- **Open source**: No licensing costs

### Schema

```sql
CREATE TABLE certificates (
    cert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject TEXT NOT NULL,
    sans TEXT[],
    serial_number TEXT UNIQUE NOT NULL,
    key_reference TEXT NOT NULL,
    issued_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    ca_name TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'revoked', 'expired')),
    revoked_at TIMESTAMP,
    revocation_reason TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_expiry ON certificates(expires_at) WHERE status = 'active';
CREATE INDEX idx_subject ON certificates USING gin(to_tsvector('english', subject));
CREATE INDEX idx_serial ON certificates(serial_number);
CREATE INDEX idx_status ON certificates(status);
```

### Integration

```python
import psycopg2

class InventoryAgent:
    def __init__(self, db_config):
        self.conn = psycopg2.connect(**db_config)
    
    def store_certificate(self, cert_data):
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO certificates 
            (subject, sans, serial_number, key_reference, 
             expires_at, ca_name, policy_version, status, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING cert_id
        """, (
            cert_data['subject'],
            cert_data['sans'],
            cert_data['serial'],
            cert_data['key_reference'],
            cert_data['expiry'],
            cert_data['ca'],
            cert_data['policy_version'],
            'active',
            json.dumps(cert_data.get('metadata', {}))
        ))
        cert_id = cursor.fetchone()[0]
        self.conn.commit()
        return cert_id
    
    def find_expiring(self, days):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT cert_id, subject, expires_at
            FROM certificates
            WHERE status = 'active'
            AND expires_at <= NOW() + INTERVAL '%s days'
            ORDER BY expires_at ASC
        """, (days,))
        return cursor.fetchall()
```

### Encryption at Rest

```sql
-- Encrypt sensitive fields
CREATE EXTENSION pgcrypto;

-- Store encrypted metadata
UPDATE certificates 
SET metadata = pgp_sym_encrypt(metadata::text, encryption_key)
WHERE cert_id = 'cert-1234';

-- Decrypt when needed
SELECT pgp_sym_decrypt(metadata, encryption_key) 
FROM certificates 
WHERE cert_id = 'cert-1234';
```

---

## 5. Audit Logging: AWS CloudWatch / Splunk

### What It Does

Captures all PKI operations in immutable, searchable logs.

### Why CloudWatch/Splunk?

- **Immutable**: Logs can't be modified or deleted
- **Tamper-evident**: Cryptographically signed
- **Retention**: 7+ years for compliance
- **Real-time alerts**: Trigger on policy violations
- **Searchable**: Query logs for audits

### Integration

#### AWS CloudWatch

```python
import boto3
import json
from datetime import datetime

class AuditAgent:
    def __init__(self):
        self.logs = boto3.client('logs')
        self.log_group = '/pki/audit'
        self.log_stream = f'stream-{datetime.now().strftime("%Y%m%d")}'
    
    def log_event(self, event_type, agent, details):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "agent": agent,
            "details": details
        }
        
        self.logs.put_log_events(
            logGroupName=self.log_group,
            logStreamName=self.log_stream,
            logEvents=[{
                'timestamp': int(datetime.now().timestamp() * 1000),
                'message': json.dumps(log_entry)
            }]
        )
```

#### Splunk

```python
import requests

class AuditAgent:
    def __init__(self, splunk_url, token):
        self.splunk_url = splunk_url
        self.token = token
    
    def log_event(self, event_type, agent, details):
        event = {
            "time": datetime.utcnow().timestamp(),
            "source": "pki-orchestrator",
            "sourcetype": "pki_audit",
            "event": {
                "event_type": event_type,
                "agent": agent,
                "details": details
            }
        }
        
        requests.post(
            f"{self.splunk_url}/services/collector/event",
            headers={"Authorization": f"Splunk {self.token}"},
            json=event
        )
```

### Log Format

```json
{
  "timestamp": "2025-01-18T14:32:15.123Z",
  "event_type": "CERTIFICATE_ISSUED",
  "request_id": "req-1234",
  "agent": "Certificate",
  "user": "alice",
  "details": {
    "cert_id": "cert-5678",
    "subject": "CN=api.example.com",
    "serial": "4A:3F:2B:...",
    "ca": "Internal-CA-Prod",
    "policy_version": "v2.3"
  },
  "success": true
}
```

### Retention Policy

```
Standard logs:      90 days
Compliance logs:    7 years (2,555 days)
Security incidents: Indefinite
```

---

## 6. Monitoring & Alerting: Prometheus + Grafana

### What It Does

Real-time metrics on PKI operations and health.

### Metrics Collected

```python
from prometheus_client import Counter, Gauge, Histogram

# Counters
cert_issued = Counter('pki_certificates_issued_total', 'Total certificates issued')
cert_revoked = Counter('pki_certificates_revoked_total', 'Total certificates revoked')
policy_violations = Counter('pki_policy_violations_total', 'Policy check failures')

# Gauges
active_certs = Gauge('pki_active_certificates', 'Number of active certificates')
expiring_soon = Gauge('pki_expiring_certificates', 'Certificates expiring in 30 days')

# Histograms
issuance_duration = Histogram('pki_issuance_duration_seconds', 'Time to issue certificate')
```

### Alerts

```yaml
# prometheus-alerts.yml
groups:
  - name: pki_alerts
    rules:
      - alert: CertificatesExpiringSoon
        expr: pki_expiring_certificates > 10
        for: 1h
        annotations:
          summary: "{{ $value }} certificates expiring in 30 days"
      
      - alert: HighPolicyViolationRate
        expr: rate(pki_policy_violations_total[5m]) > 0.1
        for: 10m
        annotations:
          summary: "High rate of policy violations detected"
      
      - alert: CAUnavailable
        expr: up{job="certificate-authority"} == 0
        for: 5m
        annotations:
          summary: "Certificate Authority is down"
```

---

## Tool Selection Matrix

| Need | Tool | Why |
|------|------|-----|
| **Key generation** | Vault/HSM | FIPS compliance, key never exported |
| **CSR creation** | OpenSSL | Industry standard, universal compatibility |
| **CA (internal)** | EJBCA | Full control, customizable |
| **CA (public)** | Let's Encrypt | Free, automated, browser-trusted |
| **Certificate DB** | PostgreSQL | ACID, JSON support, partitioning |
| **Audit logs** | CloudWatch/Splunk | Immutable, searchable, retention |
| **Metrics** | Prometheus | Real-time, alerting, open source |
| **Dashboards** | Grafana | Visualization, drill-down |

---

## Integration Architecture

```
┌────────────────────────────────────────────────┐
│         AI Orchestration Layer                 │
│  (Claude + Specialized Agents)                 │
└───┬─────┬──────┬──────┬──────┬────────────────┘
    │     │      │      │      │
    │     │      │      │      │
    ▼     ▼      ▼      ▼      ▼
┌──────┬──────┬──────┬──────┬──────┐
│Vault │OpenSSL│ CA  │ DB   │ Logs │  ◄── Trusted Tools
└──┬───┴───┬──┴───┬──┴───┬──┴───┬──┘
   │       │      │      │      │
   │       │      │      │      │
   ▼       ▼      ▼      ▼      ▼
┌────────────────────────────────────┐
│    Cryptographic Operations        │
│  (Keys, CSRs, Certs, Storage)      │
└────────────────────────────────────┘
```

**Key Principle**: AI never directly touches crypto. All operations flow through battle-tested, audited tools.