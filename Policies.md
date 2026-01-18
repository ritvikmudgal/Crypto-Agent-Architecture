# Policies - Rules & Safety Guardrails

## Overview

This document defines the security policies and guardrails that govern all PKI operations. These policies are enforced programmatically by the Policy Agent before any cryptographic operation executes.

**Key Principle**: Every request must pass policy validation. No exceptions.

---

## Policy Structure

### Policy File Format

```json
{
  "version": "2.3",
  "effective_date": "2025-01-01",
  "previous_version": "2.2",
  "changelog": "Increased RSA minimum from 2048 to 3072 bits",
  "reviewed_by": "Security Team",
  "approved_by": "CISO",
  
  "algorithms": { ... },
  "certificates": { ... },
  "keys": { ... },
  "renewal": { ... },
  "revocation": { ... },
  "compliance": { ... }
}
```

All policies are:
- **Version controlled** in Git
- **Immutable** once published (new version created for changes)
- **Audited** every operation logs which policy version was used
- **Reviewed** by security team before deployment

---

## Algorithm Policies

### Allowed Algorithms

```json
"algorithms": {
  "RSA": {
    "allowed": true,
    "min_key_size": 3072,
    "max_key_size": 8192,
    "recommended_key_size": 4096,
    "reason": "NIST SP 800-57 Part 1 Revision 5"
  },
  "ECC": {
    "allowed": true,
    "allowed_curves": ["P-256", "P-384", "P-521"],
    "recommended_curve": "P-384",
    "reason": "NIST FIPS 186-4"
  },
  "DSA": {
    "allowed": false,
    "deprecation_date": "2024-01-01",
    "reason": "Weak algorithm, replaced by RSA/ECC",
    "migration_guide": "Use RSA 3072+ or ECC P-256+"
  },
  "Ed25519": {
    "allowed": true,
    "use_case": "SSH keys only",
    "reason": "Modern, fast, secure for SSH"
  }
}
```

### Validation Rules

**Rule 1: Algorithm Must Be Allowed**
```
Request: algorithm = "DSA"
Policy Check: algorithms.DSA.allowed = false
Result: REJECTED
Reason: "DSA is deprecated since 2024-01-01. Use RSA 3072+ or ECC P-256+"
```

**Rule 2: Key Size Within Bounds**
```
Request: algorithm = "RSA", key_size = 2048
Policy Check: 2048 < 3072 (min_key_size)
Result: REJECTED
Reason: "RSA key size 2048 below minimum 3072 (NIST SP 800-57)"
```

**Rule 3: ECC Curve Must Be Approved**
```
Request: algorithm = "ECC", curve = "secp256k1"
Policy Check: "secp256k1" not in allowed_curves
Result: REJECTED
Reason: "ECC curve secp256k1 not approved. Use P-256, P-384, or P-521"
```

---

## Certificate Policies

### Validity Period Constraints

```json
"certificates": {
  "validity": {
    "min_days": 1,
    "max_days": 397,
    "default_days": 90,
    "reason": "CA/Browser Forum Baseline Requirements (397 day max)"
  },
  "renewal_window": {
    "days_before_expiry": 30,
    "auto_renew": true,
    "alert_days": [30, 14, 7, 1]
  }
}
```

**Validation**:
```
Request: validity_days = 400
Policy Check: 400 > 397 (max_days)
Result: REJECTED
Reason: "Certificate validity 400 days exceeds maximum 397 days (CA/B Forum)"
```

### Subject Alternative Names (SANs)

```json
"sans": {
  "required": true,
  "max_count": 100,
  "allowed_types": ["DNS", "IP", "email"],
  "validation": {
    "dns_pattern": "^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$",
    "wildcard_allowed": true,
    "wildcard_limit": 1
  }
}
```

**Validation Rules**:

```
✓ VALID: SANs = ["api.example.com", "www.example.com"]
✓ VALID: SANs = ["*.example.com", "example.com"]
✗ INVALID: SANs = ["*.*.example.com"] (too many wildcards)
✗ INVALID: SANs = ["EXAMPLE.COM"] (uppercase not allowed)
```

### Key Usage & Extended Key Usage

```json
"key_usage": {
  "tls_server": {
    "key_usage": ["digitalSignature", "keyEncipherment"],
    "extended_key_usage": ["serverAuth"],
    "allowed": true
  },
  "tls_client": {
    "key_usage": ["digitalSignature"],
    "extended_key_usage": ["clientAuth"],
    "allowed": true
  },
  "code_signing": {
    "key_usage": ["digitalSignature"],
    "extended_key_usage": ["codeSigning"],
    "allowed": true,
    "requires_approval": true,
    "approver_role": "security-team"
  },
  "email": {
    "key_usage": ["digitalSignature", "keyEncipherment"],
    "extended_key_usage": ["emailProtection"],
    "allowed": false,
    "reason": "Use dedicated email CA"
  }
}
```

**Validation**:
```
Request: EKU = "emailProtection"
Policy Check: key_usage.email.allowed = false
Result: REJECTED
Reason: "Email certificates not allowed. Use dedicated email CA"
```

---

## Key Management Policies

### Key Generation

```json
"keys": {
  "generation": {
    "require_hsm": true,
    "allow_software_keys": false,
    "reason": "FIPS 140-2 Level 2 compliance",
    "approved_hsms": ["Vault Enterprise", "AWS CloudHSM", "YubiHSM"]
  },
  "storage": {
    "exportable": false,
    "backup_required": true,
    "backup_encryption": "AES-256-GCM",
    "backup_location": "secure-vault"
  }
}
```

**Guardrails**:

1. **Keys Must Be Generated in HSM**
   ```
   ✗ REJECTED: Software key generation
   ✓ APPROVED: Vault Transit Engine (HSM-backed)
   ```

2. **Keys Cannot Be Exported**
   ```
   Request: Export private key
   Policy Check: keys.storage.exportable = false
   Result: REJECTED
   Reason: "Private keys cannot be exported (security policy)"
   ```

### Key Rotation

```json
"rotation": {
  "max_key_age_days": 730,
  "rotation_reminder_days": [365, 90, 30],
  "force_rotation": true,
  "reason": "Best practice: rotate every 2 years"
}
```

**Enforcement**:
```
Key age: 750 days
Policy Check: 750 > 730 (max_key_age_days)
Result: Force rotation required
Action: New certificate issuance requires new key generation
```

---

## Renewal Policies

### Automatic Renewal

```json
"renewal": {
  "auto_renew_enabled": true,
  "days_before_expiry": 30,
  "max_renewal_attempts": 3,
  "retry_interval_hours": 24,
  "reuse_key": {
    "allowed": true,
    "max_reuse_count": 3,
    "reason": "Limit key reuse to 3 certificates"
  }
}
```

**Renewal Logic**:

```
Certificate expires: 2025-02-18
Current date: 2025-01-19
Days until expiry: 30 days

Policy Check: 30 days ≤ 30 (days_before_expiry)
Action: Trigger automatic renewal

Renewal checks:
1. Is certificate still active? ✓
2. Can reuse existing key? Check reuse count
   - Current reuse: 2
   - Max reuse: 3
   - Result: ✓ Can reuse key
3. Same validity period allowed? ✓
4. Subject/SANs unchanged? ✓

Proceed with renewal
```

### Manual Renewal Restrictions

```json
"manual_renewal": {
  "min_days_before_expiry": 90,
  "reason": "Prevent unnecessary early renewals",
  "override_requires": "security-team-approval"
}
```

**Enforcement**:
```
Certificate expires: 2025-06-01
Current date: 2025-01-18
Days until expiry: 134 days

Operator: "Renew this certificate now"
Policy Check: 134 > 90 (min_days_before_expiry)
Result: REJECTED
Reason: "Certificate has 134 days remaining. Renewals allowed 90 days before expiry"
Override: Contact security team for approval
```

---

## Revocation Policies

### Revocation Reasons

```json
"revocation": {
  "valid_reasons": [
    "keyCompromise",
    "certificateHold",
    "superseded",
    "cessationOfOperation",
    "affiliationChanged"
  ],
  "immediate_revocation_reasons": [
    "keyCompromise",
    "caCompromise"
  ],
  "requires_approval": {
    "keyCompromise": false,
    "certificateHold": true,
    "superseded": true
  }
}
```

**Validation**:

```
Request: Revoke cert-1234, reason = "testing"
Policy Check: "testing" not in valid_reasons
Result: REJECTED
Reason: "Invalid revocation reason. Must be: keyCompromise, certificateHold, superseded, cessationOfOperation, affiliationChanged"
```

**Approval Requirements**:

```
Request: Revoke cert-1234, reason = "keyCompromise"
Policy Check: requires_approval.keyCompromise = false
Result: APPROVED (no approval needed for key compromise)

Request: Revoke cert-5678, reason = "superseded"
Policy Check: requires_approval.superseded = true
Result: Requires security team approval
```

### Key Destruction on Revocation

```json
"key_destruction": {
  "destroy_on_revocation": {
    "keyCompromise": true,
    "certificateHold": false,
    "superseded": false
  },
  "destruction_delay_hours": 24,
  "reason": "24-hour grace period for recovery"
}
```

---

## Compliance Policies

### Audit Requirements

```json
"compliance": {
  "audit_logging": {
    "required": true,
    "log_level": "full",
    "retention_days": 2555,
    "reason": "SOC2 requires 7-year retention"
  },
  "frameworks": {
    "SOC2": {
      "enabled": true,
      "controls": ["CC6.1", "CC6.6", "CC7.2"]
    },
    "PCI-DSS": {
      "enabled": true,
      "requirements": ["3.6", "8.2.1"]
    },
    "NIST": {
      "enabled": true,
      "publications": ["SP 800-57", "SP 800-131A"]
    }
  }
}
```

### Access Control

```json
"access_control": {
  "roles": {
    "operator": {
      "can_request_cert": true,
      "can_renew_cert": true,
      "can_revoke_cert": false,
      "can_modify_policy": false
    },
    "security_team": {
      "can_request_cert": true,
      "can_renew_cert": true,
      "can_revoke_cert": true,
      "can_modify_policy": false
    },
    "admin": {
      "can_request_cert": true,
      "can_renew_cert": true,
      "can_revoke_cert": true,
      "can_modify_policy": true,
      "requires_mfa": true
    }
  }
}
```

**Enforcement**:
```
User: alice (role: operator)
Request: Revoke certificate cert-1234
Policy Check: operator.can_revoke_cert = false
Result: REJECTED
Reason: "Revocation requires security_team or admin role"
```

---

## Guardrails Implementation

### How Guardrails Work

```python
# Policy Agent enforces guardrails

class PolicyAgent:
    def validate_request(self, request, user_role):
        guardrails = [
            self.check_algorithm,
            self.check_key_size,
            self.check_validity_period,
            self.check_key_usage,
            self.check_san_format,
            self.check_user_permissions
        ]
        
        for guardrail in guardrails:
            passed, reason = guardrail(request, user_role)
            if not passed:
                return {
                    "approved": False,
                    "guardrail_failed": guardrail.__name__,
                    "reason": reason,
                    "policy_version": self.policy['version']
                }
        
        return {
            "approved": True,
            "policy_version": self.policy['version']
        }
```

### Guardrail Hierarchy

```
┌─────────────────────────────────────────────────┐
│ Level 1: Hard Limits (Cannot Be Overridden)    │
├─────────────────────────────────────────────────┤
│ • No crypto operations in AI                   │
│ • Keys must be HSM-generated                   │
│ • Private keys cannot be exported              │
│ • Deprecated algorithms blocked                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Level 2: Policy Limits (Require Approval)      │
├─────────────────────────────────────────────────┤
│ • Validity period > 397 days                   │
│ • Key size < minimum                           │
│ • Early renewal (>90 days remaining)           │
│ • Code signing certificates                    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Level 3: Best Practice (Warnings Only)         │
├─────────────────────────────────────────────────┤
│ • Key size not recommended (e.g., RSA 3072)    │
│ • Validity period very short (<7 days)         │
│ • Many SANs (>10)                              │
└─────────────────────────────────────────────────┘
```

---

## Policy Versioning

### Version History

```json
{
  "versions": [
    {
      "version": "2.3",
      "effective_date": "2025-01-01",
      "changes": [
        "Increased RSA minimum from 2048 to 3072",
        "Added ECC P-521 to allowed curves",
        "Reduced max validity from 825 to 397 days (CA/B Forum)"
      ]
    },
    {
      "version": "2.2",
      "effective_date": "2024-06-01",
      "changes": [
        "Deprecated DSA algorithm",
        "Added Ed25519 for SSH use"
      ]
    },
    {
      "version": "2.1",
      "effective_date": "2024-01-01",
      "changes": [
        "Initial policy framework"
      ]
    }
  ]
}
```

### Version Selection Logic

```python
def get_applicable_policy(request_date):
    """
    Returns the policy version that was effective on request_date.
    """
    for version in policy_versions:
        if request_date >= version['effective_date']:
            return version
    
    # Fallback to oldest version
    return policy_versions[-1]
```

**Why this matters**: Audit trail can verify that a certificate issued 6 months ago was compliant with the policy in effect at that time, even if policy has since changed.

---

## Emergency Policy Override

### When Overrides Are Allowed

```json
"emergency_override": {
  "enabled": true,
  "requires": [
    "Two approvers from security team",
    "Written justification",
    "Incident ticket number"
  ],
  "valid_duration_hours": 24,
  "audit_alert": true,
  "examples": [
    "Production outage requires immediate cert issuance",
    "Security incident requires emergency revocation"
  ]
}
```

### Override Process

```
1. Operator submits override request
2. System generates approval ticket
3. Two security team members approve
4. Override is granted for 24 hours
5. All actions under override are flagged in audit log
6. Security team reviews all override actions next day
```

**Audit Entry**:
```json
{
  "event_type": "EMERGENCY_OVERRIDE_USED",
  "timestamp": "2025-01-18T23:45:00Z",
  "request_id": "req-9999",
  "override_reason": "Production API down, need cert immediately",
  "approved_by": ["alice", "bob"],
  "incident_ticket": "INC-12345",
  "policy_violation": "Issued cert with 2048-bit key (below 3072 minimum)",
  "override_expiry": "2025-01-19T23:45:00Z",
  "follow_up_required": true
}
```

---

## Policy Update Process

### How Policies Are Updated

```
1. Security team proposes policy change
   ↓
2. Review by stakeholders (ops, dev, compliance)
   ↓
3. Testing in staging environment
   ↓
4. CISO approval
   ↓
5. Version increment (2.3 → 2.4)
   ↓
6. Commit to Git with changelog
   ↓
7. Deploy to production (with rollback plan)
   ↓
8. Monitor impact for 7 days
   ↓
9. Document lessons learned
```

### Backward Compatibility

**Question**: What happens to existing certificates when policy changes?

**Answer**: Existing certificates are grandfathered under old policy until renewal.

```
Example:
- Jan 1, 2024: Policy v2.2 allows RSA 2048
- Cert issued: Jan 15, 2024 with RSA 2048 ✓
- Jan 1, 2025: Policy v2.3 requires RSA 3072
- Cert still valid until expiry (Jan 15, 2025)
- Renewal must use RSA 3072
```

---

## Key Takeaways

1. **Policies are code**: JSON files in Git, version controlled
2. **Policies are guardrails**: Enforced before any operation
3. **No exceptions**: Even emergency overrides are audited
4. **Backward compatible**: Old certs valid under old policy
5. **Continuously reviewed**: Updated as standards evolve

**The Policy Agent ensures that no cryptographic operation violates security rules, even if Claude suggests it.**