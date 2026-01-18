# Workflows - Step-by-Step Operations

## Overview

This document describes how PKI operations flow through our multi-agent system. Each workflow shows the exact sequence of agent interactions, decision points, and tool invocations.

---

## Workflow 1: Certificate Issuance

### Trigger
Operator requests: "Issue TLS certificate for api.example.com with RSA 4096, 90-day validity"

### Steps

```
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Request Reception                              │
└─────────────────────────────────────────────────────────┘

Operator
    │
    │ "Issue cert for api.example.com, RSA 4096, 90 days"
    │
    ▼
Orchestrator Agent
    │
    │ Parses request and extracts:
    │ - Domain: api.example.com
    │ - Algorithm: RSA
    │ - Key Size: 4096
    │ - Validity: 90 days
    │ - SANs: [api.example.com, www.example.com]
    │
    ▼
Creates workflow plan:
[Policy Check] → [Key Gen] → [CSR] → [CA Submit] → [Inventory]
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 2: Policy Validation                              │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    │ "Policy Agent, validate this request"
    │
    ▼
Policy Agent
    │
    ├─ Check: Algorithm = RSA (allowed?) ✓
    ├─ Check: Key Size = 4096 (≥ 3072?) ✓
    ├─ Check: Validity = 90 days (≤ 397?) ✓
    ├─ Check: EKU = serverAuth (allowed?) ✓
    │
    ▼
Decision: APPROVED
Reason: "All checks passed under policy v2.3"
    │
    │ Send approval to Orchestrator
    │
    ▼
Audit Agent
    │
    │ Log: [Policy Check PASSED]
    │       Request ID: req-1234
    │       Policy Version: v2.3
    │       Timestamp: 2025-01-18T14:32:15Z
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 3: Key Generation                                 │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    │ "Key Management Agent, generate RSA 4096"
    │ Key name: api-example-com
    │
    ▼
Key Management Agent
    │
    ├─ Construct Vault API request:
    │  POST /v1/transit/keys/api-example-com
    │  {
    │    "type": "rsa-4096",
    │    "exportable": false
    │  }
    │
    ▼
Vault/HSM
    │
    │ Generate key pair internally
    │ Store in hardware security module
    │ Return key reference (NOT the key itself)
    │
    ▼
Key Management Agent
    │
    │ Receives: transit/keys/api-example-com/v1
    │ Return to Orchestrator
    │
    ▼
Audit Agent
    │
    │ Log: [Key Generated]
    │       Key Reference: transit/keys/api-example-com
    │       Algorithm: RSA-4096
    │       Actor: orchestrator
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 4: CSR Creation                                   │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    │ "Certificate Agent, create CSR"
    │ Subject: CN=api.example.com
    │ SANs: [api.example.com, www.example.com]
    │ Key ref: transit/keys/api-example-com
    │
    ▼
Certificate Agent
    │
    ├─ Get public key from Vault
    │  GET /v1/transit/keys/api-example-com
    │
    ▼
Vault
    │
    │ Return public key (PEM format)
    │
    ▼
Certificate Agent
    │
    ├─ Create OpenSSL config:
    │  [req]
    │  distinguished_name = req_distinguished_name
    │  req_extensions = v3_req
    │  
    │  [req_distinguished_name]
    │  CN = api.example.com
    │  
    │  [v3_req]
    │  subjectAltName = @alt_names
    │  
    │  [alt_names]
    │  DNS.1 = api.example.com
    │  DNS.2 = www.example.com
    │
    ├─ Execute OpenSSL:
    │  openssl req -new -key public_key.pem -config csr.conf
    │
    ▼
OpenSSL
    │
    │ Generate CSR (PEM format)
    │
    ▼
Certificate Agent
    │
    │ Validate CSR syntax
    │ Verify subject and SANs
    │ Return CSR to Orchestrator
    │
    ▼
Audit Agent
    │
    │ Log: [CSR Created]
    │       Subject: CN=api.example.com
    │       SANs: 2 entries
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 5: Certificate Issuance                           │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    │ "Certificate Agent, submit CSR to CA"
    │ CSR: <base64-encoded>
    │ Validity: 90 days
    │
    ▼
Certificate Agent
    │
    ├─ Prepare CA request:
    │  POST /api/v1/certificates/issue
    │  {
    │    "csr": "<pem>",
    │    "validity_days": 90,
    │    "profile": "tls-server"
    │  }
    │
    ▼
Certificate Authority
    │
    ├─ Validate CSR
    ├─ Check CA policies
    ├─ Sign certificate
    │
    ▼
Returns:
    │
    │ {
    │   "certificate": "<pem>",
    │   "serial_number": "4A:3F:2B:...",
    │   "not_before": "2025-01-18T14:32:00Z",
    │   "not_after": "2025-04-18T14:32:00Z"
    │ }
    │
    ▼
Certificate Agent
    │
    ├─ Validate certificate chain
    ├─ Verify signature
    ├─ Check expiry dates
    │
    │ Return to Orchestrator
    │
    ▼
Audit Agent
    │
    │ Log: [Certificate Issued]
    │       Serial: 4A:3F:2B:...
    │       CA: Internal-CA-Prod
    │       Validity: 2025-01-18 to 2025-04-18
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 6: Inventory Update                               │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    │ "Inventory Agent, store certificate metadata"
    │
    ▼
Inventory Agent
    │
    ├─ Generate cert ID: cert-20250118143215
    │
    ├─ Prepare database insert:
    │  INSERT INTO certificates (
    │    cert_id, subject, sans, serial_number,
    │    key_reference, issued_at, expires_at,
    │    ca_name, policy_version, status
    │  ) VALUES (...)
    │
    ▼
PostgreSQL Database
    │
    │ Store record
    │ Set up expiry trigger (alert 30 days before)
    │
    ▼
Inventory Agent
    │
    │ Return cert_id to Orchestrator
    │
    ▼
Audit Agent
    │
    │ Log: [Inventory Updated]
    │       Cert ID: cert-20250118143215
    │       Expiry Monitoring: Enabled
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 7: Response to Operator                           │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    ├─ Aggregate all results:
    │  - Policy: Approved
    │  - Key: Generated and stored
    │  - CSR: Created
    │  - Certificate: Issued
    │  - Inventory: Updated
    │
    ▼
Return to Operator:
{
  "success": true,
  "cert_id": "cert-20250118143215",
  "certificate": "<pem-encoded>",
  "serial_number": "4A:3F:2B:...",
  "expires_at": "2025-04-18T14:32:00Z",
  "audit_reference": "req-1234"
}
```

### Timeline

| Step | Agent | Duration | Cumulative |
|------|-------|----------|------------|
| 1. Parse request | Orchestrator | ~100ms | 100ms |
| 2. Policy validation | Policy | ~50ms | 150ms |
| 3. Key generation | Key Mgmt + Vault | ~500ms | 650ms |
| 4. CSR creation | Certificate + OpenSSL | ~200ms | 850ms |
| 5. CA issuance | Certificate + CA | ~2000ms | 2850ms |
| 6. Inventory update | Inventory + DB | ~100ms | 2950ms |
| **Total** | | | **~3 seconds** |

---

## Workflow 2: Certificate Renewal

### Trigger
- Automated: Inventory Agent detects cert expiring in 30 days
- Manual: Operator requests renewal

### Steps

```
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Identify Expiring Certificate                  │
└─────────────────────────────────────────────────────────┘

Inventory Agent (scheduled job)
    │
    ├─ Query database:
    │  SELECT cert_id, subject, key_reference, expires_at
    │  FROM certificates
    │  WHERE expires_at <= NOW() + INTERVAL '30 days'
    │  AND status = 'active'
    │
    ▼
Results:
    │
    │ cert-5678: api.example.com (expires in 28 days)
    │
    ▼
Triggers renewal workflow for each cert
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 2: Orchestrator Plans Renewal                     │
└─────────────────────────────────────────────────────────┘

Orchestrator receives renewal trigger
    │
    ├─ Load existing cert details:
    │  - Subject: api.example.com
    │  - Key reference: transit/keys/api-example-com
    │  - Algorithm: RSA-4096
    │  - Previous validity: 90 days
    │
    ├─ Decision: Reuse key or generate new?
    │  → Default: Reuse existing key
    │
    ▼
Workflow plan:
[Policy Check] → [Reuse Key] → [CSR] → [CA Submit] → [Update Inventory]
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 3: Policy Validation for Renewal                  │
└─────────────────────────────────────────────────────────┘

Policy Agent
    │
    ├─ Check: Can reuse existing key? ✓
    ├─ Check: Same validity period allowed? ✓
    ├─ Check: Current policy still permits RSA-4096? ✓
    │
    ▼
Decision: APPROVED
Note: "Renewal under same parameters as original issuance"
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 4: Create CSR with Existing Key                   │
└─────────────────────────────────────────────────────────┘

Certificate Agent
    │
    ├─ Use existing key reference: transit/keys/api-example-com
    ├─ Get public key from Vault
    ├─ Generate new CSR (same subject/SANs)
    │
    ▼
New CSR created
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 5: Issue Renewed Certificate                      │
└─────────────────────────────────────────────────────────┘

Certificate Agent → CA
    │
    │ Submit CSR for renewal
    │
    ▼
CA issues new certificate
    │
    │ New serial: 6D:8A:1C:...
    │ New expiry: 2025-05-18 (90 days from today)
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 6: Update Inventory                               │
└─────────────────────────────────────────────────────────┘

Inventory Agent
    │
    ├─ Update existing record:
    │  UPDATE certificates
    │  SET serial_number = '6D:8A:1C:...',
    │      issued_at = NOW(),
    │      expires_at = '2025-05-18',
    │      renewed_from = 'cert-5678'
    │  WHERE cert_id = 'cert-5678'
    │
    ▼
Certificate renewed successfully
```

---

## Workflow 3: Certificate Revocation

### Trigger
Operator requests: "Revoke certificate cert-5678 - reason: key compromise"

### Steps

```
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Validate Revocation Request                    │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    │ Parse revocation request
    │
    ▼
Policy Agent
    │
    ├─ Verify cert exists and is active
    ├─ Validate reason code (key compromise = valid)
    ├─ Check operator has revocation authority
    │
    ▼
APPROVED for revocation
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 2: Submit to CA for Revocation                    │
└─────────────────────────────────────────────────────────┘

Certificate Agent
    │
    ├─ Prepare revocation request:
    │  POST /api/v1/certificates/revoke
    │  {
    │    "serial_number": "4A:3F:2B:...",
    │    "reason": "keyCompromise",
    │    "revocation_date": "2025-01-18T15:00:00Z"
    │  }
    │
    ▼
CA adds to CRL (Certificate Revocation List)
CA updates OCSP (Online Certificate Status Protocol)
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 3: Update Inventory                               │
└─────────────────────────────────────────────────────────┘

Inventory Agent
    │
    ├─ UPDATE certificates
    │  SET status = 'revoked',
    │      revoked_at = NOW(),
    │      revocation_reason = 'keyCompromise'
    │  WHERE cert_id = 'cert-5678'
    │
    ▼
Certificate marked as revoked
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 4: Key Destruction (Optional)                     │
└─────────────────────────────────────────────────────────┘

For key compromise:
    │
    ▼
Key Management Agent
    │
    ├─ DELETE /v1/transit/keys/api-example-com
    │
    ▼
Vault destroys key material
```

---

## Workflow 4: Bulk Certificate Issuance

### Trigger
Operator: "Issue certificates for api-1 through api-10, all RSA 4096, 90 days"

### Steps

```
┌─────────────────────────────────────────────────────────┐
│ STEP 1: Parse Bulk Request                             │
└─────────────────────────────────────────────────────────┘

Orchestrator
    │
    ├─ Use Claude to understand request:
    │  "Generate 10 certificates with pattern api-{1..10}"
    │
    ▼
Creates list of certificate requests:
    │
    ├─ api-1.example.com
    ├─ api-2.example.com
    ├─ ...
    └─ api-10.example.com
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 2: Validate All Requests                          │
└─────────────────────────────────────────────────────────┘

Policy Agent
    │
    ├─ Validate request 1: ✓
    ├─ Validate request 2: ✓
    ├─ ...
    └─ Validate request 10: ✓
    │
    ▼
All requests approved
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 3: Parallel Key Generation                        │
└─────────────────────────────────────────────────────────┘

Key Management Agent
    │
    ├─ Create keys in parallel:
    │  ├─ Thread 1: api-1 → Vault
    │  ├─ Thread 2: api-2 → Vault
    │  ├─ ...
    │  └─ Thread 10: api-10 → Vault
    │
    ▼
10 keys generated concurrently
Total time: ~1 second (vs 10 seconds sequential)
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 4: Parallel CSR Creation                          │
└─────────────────────────────────────────────────────────┘

Certificate Agent
    │
    ├─ Create CSRs in parallel (10 OpenSSL processes)
    │
    ▼
10 CSRs ready
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 5: Parallel CA Submission                         │
└─────────────────────────────────────────────────────────┘

Certificate Agent
    │
    ├─ Submit all CSRs to CA (parallel requests)
    │
    ▼
10 certificates issued
```

```
┌─────────────────────────────────────────────────────────┐
│ STEP 6: Batch Inventory Update                         │
└─────────────────────────────────────────────────────────┘

Inventory Agent
    │
    ├─ Batch insert:
    │  INSERT INTO certificates (...) VALUES
    │    (cert-1, ...),
    │    (cert-2, ...),
    │    ...
    │    (cert-10, ...)
    │
    ▼
All certificates tracked
```

### Performance Comparison

| Approach | Time |
|----------|------|
| Sequential (one at a time) | ~30 seconds |
| Parallel (our approach) | ~5 seconds |

---

## Error Handling Workflows

### Scenario: CA is Unavailable

```
Certificate Agent attempts CA submission
    │
    ▼
CA returns: 503 Service Unavailable
    │
    ▼
Certificate Agent
    │
    ├─ Retry logic:
    │  - Attempt 1: Wait 1s, retry → Failed
    │  - Attempt 2: Wait 2s, retry → Failed
    │  - Attempt 3: Wait 4s, retry → Failed
    │
    ▼
Certificate Agent reports failure to Orchestrator
    │
    ▼
Orchestrator
    │
    ├─ Log error
    ├─ Store partial state (CSR created, awaiting CA)
    ├─ Alert operator
    │
    ▼
Response to Operator:
{
  "success": false,
  "error": "CA unavailable after 3 retries",
  "state": "csr_created",
  "resume_id": "resume-1234"
}
```

### Scenario: Policy Violation

```
Policy Agent detects violation
    │
    │ Request: RSA 2048 (below minimum 3072)
    │
    ▼
Policy Agent returns: REJECTED
Reason: "Key size 2048 below minimum 3072 (policy v2.3)"
    │
    ▼
Orchestrator
    │
    ├─ Does NOT proceed with workflow
    ├─ Logs rejection
    │
    ▼
Audit Agent
    │
    │ Log: [Policy Violation]
    │       Request ID: req-5678
    │       Violation: Key size below minimum
    │       Suggested: Use RSA 3072 or higher
    │
    ▼
Response to Operator:
{
  "success": false,
  "error": "Policy violation: Key size 2048 below minimum 3072",
  "policy_version": "v2.3",
  "suggestion": "Use RSA key size ≥ 3072 bits"
}
```

---

## Scheduled Workflows

### Daily Expiry Check

```
Cron: Every day at 02:00 UTC
    │
    ▼
Inventory Agent
    │
    ├─ Query expiring certificates (30 days threshold)
    │
    ▼
For each expiring cert:
    │
    ├─ Trigger renewal workflow
    ├─ Send notification to operator
    │
    ▼
Audit Agent logs all renewals
```

### Weekly Compliance Report

```
Cron: Every Monday at 09:00 UTC
    │
    ▼
Inventory Agent
    │
    ├─ Generate report:
    │  - Total active certificates: 1,234
    │  - Expiring this month: 45
    │  - Revoked this week: 2
    │  - Policy compliance: 100%
    │
    ▼
Email report to security team
```

---

## Summary

All workflows follow the same pattern:
1. **Parse request** (Orchestrator)
2. **Validate policy** (Policy Agent)
3. **Execute operations** (Specialized agents + tools)
4. **Update inventory** (Inventory Agent)
5. **Audit everything** (Audit Agent)

This ensures consistency, auditability, and security across all PKI operations.