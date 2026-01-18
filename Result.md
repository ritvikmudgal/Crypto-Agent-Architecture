# Implementation Guide

## Overview

This document provides practical guidance for implementing the AI-driven PKI lifecycle management system. It synthesizes everything we've learned from analyzing the architecture, frameworks, and multi-agent design.

---

## Key Learnings from This Assignment

### 1. **AI Orchestrates, Never Executes Crypto**

**The Principle**: Claude plans workflows and validates logic, but cryptographic operations happen in trusted tools.

```
✓ Claude decides: "Generate RSA 4096 key"
✓ Claude calls: Vault API
✗ Claude never: Performs key generation math
```

### 2. **Multi-Agent Beats Monolithic for Security**

**The Principle**: Separation of concerns enables auditability and testability.

```
One big agent:  Hard to audit, impossible to test components
Six specialized agents: Clear responsibilities, testable independently
```

### 3. **Direct API > Frameworks for Critical Systems**

**The Principle**: Simplicity and control trump convenience for security.

```
LangChain: Abstraction layers make auditing hard
Direct Claude API: Full visibility into every call
```

### 4. **Stateless is Safer Than Stateful**

**The Principle**: Each request validated fresh against current policy.

```
With MCP context: "Do it like last time" (might violate new policy)
Without MCP: "Validate against current rules" (always compliant)
```

### 5. **Policy as Guardrails, Not Suggestions**

**The Principle**: Enforce rules programmatically before execution.

```
✓ Policy Agent: "RSA 2048 REJECTED - minimum is 3072"
✗ Claude suggesting: "You might want to use a stronger key"
```

---

## Implementation Architecture

### System Components

```
┌──────────────────────────────────────────────────────┐
│                  Operator Interface                  │
│              (CLI, API, Web Dashboard)               │
└────────────────────────┬─────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────┐
│              Orchestrator Agent (Claude)             │
│  • Parses requests                                   │
│  • Plans multi-step workflows                        │
│  • Coordinates specialized agents                    │
│  • Aggregates results                                │
└────┬────┬────┬────┬────┬─────────────────────────────┘
     │    │    │    │    │
     │    │    │    │    └────────┐
     │    │    │    │             │
     ▼    ▼    ▼    ▼    ▼        ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Policy  │ │Key Mgmt│ │Cert    │ │Inventory│ │Audit  │
│Agent   │ │Agent   │ │Agent   │ │Agent    │ │Agent  │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬─────┘ └───┬───┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Policy  │ │Vault/  │ │OpenSSL │ │Postgres│ │CloudWatch│
│Rules   │ │HSM API │ │+ CA    │ │Database│ │Logs    │
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘
```

---

## Practical Implementation Steps

### Step 1: Set Up Core Infrastructure

**What you need**:
- Claude API access (Anthropic API key)
- HashiCorp Vault or AWS KMS (key management)
- OpenSSL (local or containerized)
- Certificate Authority (internal CA, Let's Encrypt ACME, or cloud CA)
- PostgreSQL database
- Log aggregation system (CloudWatch, Splunk, or ELK)

### Step 2: Define Policy Rules

Create `policies/security_policy.json`:

```json
{
  "version": "2.3",
  "effective_date": "2025-01-01",
  "algorithms": {
    "RSA": {
      "min_key_size": 3072,
      "max_key_size": 8192,
      "allowed": true
    },
    "ECC": {
      "allowed_curves": ["P-256", "P-384", "P-521"],
      "allowed": true
    },
    "DSA": {
      "allowed": false,
      "deprecation_reason": "Weak algorithm"
    }
  },
  "certificates": {
    "max_validity_days": 397,
    "min_validity_days": 1,
    "allowed_key_usages": [
      "digitalSignature",
      "keyEncipherment",
      "dataEncipherment"
    ],
    "allowed_extended_key_usages": [
      "serverAuth",
      "clientAuth",
      "codeSigning"
    ]
  },
  "renewal": {
    "days_before_expiry": 30,
    "auto_renew_enabled": true
  }
}
```

Version this in Git for auditability.

### Step 3: Implement Policy Agent

**Purpose**: Validates requests against policy rules.

```python
# policy_agent.py

import json
from typing import Dict, Any, Tuple

class PolicyAgent:
    def __init__(self, policy_path: str):
        with open(policy_path, 'r') as f:
            self.policy = json.load(f)
    
    def validate_request(self, request: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate request against security policy.
        Returns (approved: bool, reason: str)
        """
        algorithm = request.get('algorithm')
        key_size = request.get('key_size')
        validity_days = request.get('validity_days')
        
        # Check algorithm
        if algorithm not in self.policy['algorithms']:
            return False, f"Algorithm {algorithm} not in policy"
        
        algo_policy = self.policy['algorithms'][algorithm]
        if not algo_policy.get('allowed'):
            reason = algo_policy.get('deprecation_reason', 'Not allowed')
            return False, f"Algorithm {algorithm} not allowed: {reason}"
        
        # Check key size for RSA
        if algorithm == "RSA":
            min_size = algo_policy['min_key_size']
            max_size = algo_policy['max_key_size']
            if key_size < min_size:
                return False, f"Key size {key_size} below minimum {min_size}"
            if key_size > max_size:
                return False, f"Key size {key_size} above maximum {max_size}"
        
        # Check validity period
        max_validity = self.policy['certificates']['max_validity_days']
        min_validity = self.policy['certificates']['min_validity_days']
        if validity_days > max_validity:
            return False, f"Validity {validity_days} exceeds max {max_validity}"
        if validity_days < min_validity:
            return False, f"Validity {validity_days} below min {min_validity}"
        
        # All checks passed
        return True, f"Approved under policy v{self.policy['version']}"
```

### Step 4: Implement Key Management Agent

**Purpose**: Orchestrates key generation via Vault/HSM.

```python
# key_management_agent.py

import hvac  # HashiCorp Vault client
from typing import Dict, Any

class KeyManagementAgent:
    def __init__(self, vault_url: str, vault_token: str):
        self.client = hvac.Client(url=vault_url, token=vault_token)
    
    def generate_key(self, key_name: str, algorithm: str, key_size: int) -> Dict[str, Any]:
        """
        Generate key pair in Vault Transit Engine.
        Returns key reference (never the actual key material).
        """
        try:
            # Create key in Vault Transit
            self.client.secrets.transit.create_key(
                name=key_name,
                key_type=f"{algorithm.lower()}-{key_size}",
                exportable=False  # Never allow key export
            )
            
            # Return reference to key
            return {
                "success": True,
                "key_reference": f"transit/keys/{key_name}",
                "algorithm": algorithm,
                "key_size": key_size
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_public_key(self, key_name: str) -> str:
        """
        Retrieve public key for CSR generation.
        """
        try:
            result = self.client.secrets.transit.read_key(name=key_name)
            # Extract public key from latest version
            latest_version = max(result['data']['keys'].keys())
            public_key = result['data']['keys'][latest_version]['public_key']
            return public_key
        except Exception as e:
            raise Exception(f"Failed to get public key: {e}")
```

### Step 5: Implement Certificate Agent

**Purpose**: Handles CSR creation and certificate operations.

```python
# certificate_agent.py

import subprocess
from typing import Dict, Any
import requests

class CertificateAgent:
    def __init__(self, ca_url: str, ca_api_key: str):
        self.ca_url = ca_url
        self.ca_api_key = ca_api_key
    
    def create_csr(self, subject: str, public_key: str, sans: list) -> str:
        """
        Create Certificate Signing Request using OpenSSL.
        """
        # Create OpenSSL config
        config = f"""
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req

[req_distinguished_name]
CN = {subject}

[v3_req]
subjectAltName = @alt_names

[alt_names]
"""
        for i, san in enumerate(sans, 1):
            config += f"DNS.{i} = {san}\n"
        
        # Write config to temp file
        with open('/tmp/csr.conf', 'w') as f:
            f.write(config)
        
        # Write public key to temp file
        with open('/tmp/public_key.pem', 'w') as f:
            f.write(public_key)
        
        # Generate CSR using OpenSSL
        result = subprocess.run([
            'openssl', 'req', '-new',
            '-key', '/tmp/public_key.pem',
            '-config', '/tmp/csr.conf',
            '-out', '/tmp/request.csr'
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"CSR creation failed: {result.stderr}")
        
        # Read and return CSR
        with open('/tmp/request.csr', 'r') as f:
            return f.read()
    
    def submit_to_ca(self, csr: str, validity_days: int) -> Dict[str, Any]:
        """
        Submit CSR to Certificate Authority.
        """
        try:
            response = requests.post(
                f"{self.ca_url}/api/v1/certificates/issue",
                headers={"Authorization": f"Bearer {self.ca_api_key}"},
                json={
                    "csr": csr,
                    "validity_days": validity_days
                }
            )
            response.raise_for_status()
            
            cert_data = response.json()
            return {
                "success": True,
                "certificate": cert_data['certificate'],
                "serial": cert_data['serial_number'],
                "expiry": cert_data['not_after']
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
```

### Step 6: Implement Inventory Agent

**Purpose**: Tracks cryptographic assets in database.

```python
# inventory_agent.py

import psycopg2
from datetime import datetime
from typing import Dict, Any

class InventoryAgent:
    def __init__(self, db_config: Dict[str, str]):
        self.conn = psycopg2.connect(**db_config)
    
    def store_certificate(self, cert_data: Dict[str, Any]) -> str:
        """
        Store certificate metadata in inventory database.
        """
        cursor = self.conn.cursor()
        
        # Generate cert ID
        cert_id = f"cert-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Insert into database
        cursor.execute("""
            INSERT INTO certificates 
            (cert_id, subject, sans, serial_number, key_reference, 
             issued_at, expires_at, ca_name, policy_version, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            cert_id,
            cert_data['subject'],
            cert_data['sans'],
            cert_data['serial'],
            cert_data['key_reference'],
            datetime.now(),
            cert_data['expiry'],
            cert_data['ca'],
            cert_data['policy_version'],
            'active'
        ))
        
        self.conn.commit()
        cursor.close()
        
        return cert_id
    
    def get_expiring_certificates(self, days: int) -> list:
        """
        Find certificates expiring within specified days.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT cert_id, subject, expires_at
            FROM certificates
            WHERE status = 'active'
            AND expires_at <= NOW() + INTERVAL '%s days'
            ORDER BY expires_at ASC
        """, (days,))
        
        results = cursor.fetchall()
        cursor.close()
        
        return [
            {
                "cert_id": row[0],
                "subject": row[1],
                "expiry": row[2]
            }
            for row in results
        ]
```

### Step 7: Implement Audit Agent

**Purpose**: Logs all operations for compliance.

```python
# audit_agent.py

import json
import logging
from datetime import datetime
from typing import Dict, Any

class AuditAgent:
    def __init__(self, log_destination: str):
        # Configure logging to CloudWatch/Splunk/file
        logging.basicConfig(
            filename=log_destination,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('PKI_Audit')
    
    def log_event(self, event_type: str, agent: str, details: Dict[str, Any]):
        """
        Log audit event with structured data.
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "agent": agent,
            "details": details
        }
        
        self.logger.info(json.dumps(audit_entry))
    
    def log_policy_decision(self, approved: bool, reason: str, request: Dict[str, Any]):
        """
        Log policy enforcement decision.
        """
        self.log_event(
            event_type="POLICY_CHECK",
            agent="Policy",
            details={
                "approved": approved,
                "reason": reason,
                "request_params": request
            }
        )
    
    def log_certificate_issuance(self, cert_id: str, subject: str, serial: str):
        """
        Log certificate issuance.
        """
        self.log_event(
            event_type="CERT_ISSUED",
            agent="Certificate",
            details={
                "cert_id": cert_id,
                "subject": subject,
                "serial_number": serial
            }
        )
```

### Step 8: Implement Orchestrator Agent

**Purpose**: Coordinates all agents using Claude.

```python
# orchestrator_agent.py

import anthropic
import json
from typing import Dict, Any

class OrchestratorAgent:
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        
        # Initialize specialized agents
        self.policy_agent = PolicyAgent('policies/security_policy.json')
        self.key_agent = KeyManagementAgent(vault_url, vault_token)
        self.cert_agent = CertificateAgent(ca_url, ca_api_key)
        self.inventory_agent = InventoryAgent(db_config)
        self.audit_agent = AuditAgent(log_destination)
    
    def process_request(self, user_request: str) -> Dict[str, Any]:
        """
        Main orchestration logic using Claude.
        """
        # Use Claude to parse and plan
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{
                "role": "user",
                "content": f"""
You are a PKI orchestration agent. Parse this request and create a workflow plan:

Request: {user_request}

Respond with JSON containing:
- action: "issue_certificate" | "renew_certificate" | "revoke_certificate"
- parameters: {{subject, algorithm, key_size, validity_days, sans}}

Only return JSON, no explanation.
"""
            }]
        )
        
        # Parse Claude's response
        plan = json.loads(response.content[0].text)
        
        # Execute workflow based on plan
        if plan['action'] == 'issue_certificate':
            return self.issue_certificate(plan['parameters'])
        elif plan['action'] == 'renew_certificate':
            return self.renew_certificate(plan['parameters'])
        else:
            return {"error": "Unsupported action"}
    
    def issue_certificate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate certificate issuance workflow.
        """
        # Step 1: Policy validation
        approved, reason = self.policy_agent.validate_request(params)
        self.audit_agent.log_policy_decision(approved, reason, params)
        
        if not approved:
            return {"error": f"Policy violation: {reason}"}
        
        # Step 2: Generate key
        key_name = f"key-{params['subject']}"
        key_result = self.key_agent.generate_key(
            key_name, params['algorithm'], params['key_size']
        )
        
        if not key_result['success']:
            return {"error": f"Key generation failed: {key_result['error']}"}
        
        self.audit_agent.log_event("KEY_GENERATED", "KeyManagement", key_result)
        
        # Step 3: Get public key and create CSR
        public_key = self.key_agent.get_public_key(key_name)
        csr = self.cert_agent.create_csr(
            params['subject'], public_key, params.get('sans', [])
        )
        
        self.audit_agent.log_event("CSR_CREATED", "Certificate", {
            "subject": params['subject']
        })
        
        # Step 4: Submit to CA
        cert_result = self.cert_agent.submit_to_ca(csr, params['validity_days'])
        
        if not cert_result['success']:
            return {"error": f"Certificate issuance failed: {cert_result['error']}"}
        
        self.audit_agent.log_certificate_issuance(
            "pending", params['subject'], cert_result['serial']
        )
        
        # Step 5: Store in inventory
        cert_id = self.inventory_agent.store_certificate({
            "subject": params['subject'],
            "sans": params.get('sans', []),
            "serial": cert_result['serial'],
            "key_reference": key_result['key_reference'],
            "expiry": cert_result['expiry'],
            "ca": "Internal-CA",
            "policy_version": "2.3"
        })
        
        self.audit_agent.log_event("INVENTORY_UPDATED", "Inventory", {
            "cert_id": cert_id
        })
        
        # Return success
        return {
            "success": True,
            "cert_id": cert_id,
            "certificate": cert_result['certificate'],
            "serial": cert_result['serial'],
            "expiry": cert_result['expiry']
        }
```

---

## Best Practices from This Assignment

### 1. **Never Trust LLM Output Blindly**

```python
# ✗ BAD: Use LLM output directly in crypto operations
key_size = claude.generate_text("What key size?")
vault.generate_key(key_size)  # DANGEROUS

# ✓ GOOD: Validate LLM output against policy
suggested_size = claude.generate_text("What key size?")
approved, _ = policy_agent.validate({"key_size": suggested_size})
if approved:
    vault.generate_key(suggested_size)
```

### 2. **Log Everything**

```python
# Every agent action should be audited
audit_agent.log_event(event_type, agent_name, details)
```

### 3. **Use Tool Calling, Not Prompt Engineering**

```python
# ✗ BAD: Rely on prompt to trigger actions
response = claude.generate("Generate a key pair for...")
# Parse response and guess what to do

# ✓ GOOD: Use Claude's tool calling
tools = [
    {
        "name": "generate_key",
        "input_schema": {
            "algorithm": "string",
            "key_size": "integer"
        }
    }
]
response = claude.messages.create(tools=tools, ...)
# Claude explicitly calls the tool
```

### 4. **Test Each Agent Independently**

```python
def test_policy_agent():
    policy = PolicyAgent('test_policy.json')
    
    # Test weak key rejection
    approved, reason = policy.validate({
        "algorithm": "RSA",
        "key_size": 2048
    })
    assert not approved
    assert "minimum" in reason.lower()
```

### 5. **Version Your Policies**

```json
{
  "version": "2.3",
  "effective_date": "2025-01-01",
  "previous_version": "2.2",
  "changelog": "Increased RSA minimum from 2048 to 3072"
}
```

---

## Deployment Considerations

### Infrastructure Setup

```yaml
# docker-compose.yml
version: '3.8'
services:
  vault:
    image: vault:latest
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: dev-token
    ports:
      - "8200:8200"
  
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: pki_inventory
      POSTGRES_USER: pki
      POSTGRES_PASSWORD: secure_password
    volumes:
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql
  
  orchestrator:
    build: .
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      VAULT_URL: http://vault:8200
      DATABASE_URL: postgresql://pki:secure_password@postgres/pki_inventory
    depends_on:
      - vault
      - postgres
```

### Database Schema

```sql
-- schema.sql
CREATE TABLE certificates (
    cert_id VARCHAR(50) PRIMARY KEY,
    subject TEXT NOT NULL,
    sans TEXT[],
    serial_number TEXT UNIQUE NOT NULL,
    key_reference TEXT NOT NULL,
    issued_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ca_name TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'revoked', 'expired')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_expiry ON certificates(expires_at) WHERE status = 'active';
CREATE INDEX idx_subject ON certificates(subject);
```

---

## Summary of Implementation Learnings

| Concept | Key Takeaway |
|---------|--------------|
| **Multi-Agent** | Separation of concerns enables testability and auditability |
| **No Frameworks** | Direct API calls give full control for security-critical systems |
| **Stateless** | Each request validated fresh against current policy |
| **Policy First** | Enforce rules programmatically before any crypto operation |
| **Audit Everything** | Immutable logs for compliance and debugging |
| **Trust Tools** | Let Vault/OpenSSL handle crypto, AI orchestrates |

This implementation guide brings together architecture, design decisions, and practical code to build a secure, auditable, AI-driven PKI management system.