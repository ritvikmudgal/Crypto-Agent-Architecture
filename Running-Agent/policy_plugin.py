"""
Policy Enforcement MCP Plugin
Validates cryptographic operations against organizational policies
"""

from datetime import datetime, timedelta
import json

class PolicyMCPPlugin:
    """MCP Plugin for cryptographic policy enforcement"""
    
    def __init__(self):
        self.policies = self._load_default_policies()
        self.violations = []
    
    def _load_default_policies(self):
        """Load default cryptographic policies"""
        return {
            "key_generation": {
                "rsa_min_key_size": 2048,
                "rsa_allowed_sizes": [2048, 3072, 4096],
                "ecc_allowed_curves": ["SECP256R1", "SECP384R1", "SECP521R1"],
                "allowed_algorithms": ["RSA", "ECC"]
            },
            "certificate": {
                "max_validity_days": 825,  # Per CA/Browser Forum baseline
                "min_validity_days": 1,
                "require_san": True,
                "allowed_key_usages": [
                    "digitalSignature",
                    "keyEncipherment",
                    "dataEncipherment",
                    "keyAgreement",
                    "keyCertSign",
                    "cRLSign"
                ],
                "allowed_extended_key_usages": [
                    "serverAuth",
                    "clientAuth",
                    "codeSigning",
                    "emailProtection"
                ]
            },
            "naming": {
                "require_country": False,
                "require_organization": True,
                "max_common_name_length": 64,
                "allowed_countries": None  # None = all allowed
            },
            "lifecycle": {
                "renewal_warning_days": 30,
                "auto_revoke_on_compromise": True
            }
        }
    
    def get_tools(self):
        """Return MCP tool definitions"""
        return [
            {
                "name": "validate_key_policy",
                "description": "Validate key generation parameters against organizational policies.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "algorithm": {
                            "type": "string",
                            "description": "Key algorithm (RSA or ECC)"
                        },
                        "key_size": {
                            "type": "integer",
                            "description": "Key size for RSA"
                        },
                        "curve": {
                            "type": "string",
                            "description": "Curve name for ECC"
                        }
                    },
                    "required": ["algorithm"]
                }
            },
            {
                "name": "validate_certificate_policy",
                "description": "Validate certificate parameters against organizational policies.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "validity_days": {
                            "type": "integer",
                            "description": "Certificate validity period in days"
                        },
                        "common_name": {
                            "type": "string",
                            "description": "Certificate common name"
                        },
                        "organization": {
                            "type": "string",
                            "description": "Organization name"
                        },
                        "country": {
                            "type": "string",
                            "description": "Country code"
                        },
                        "key_usage": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key usage extensions"
                        },
                        "extended_key_usage": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Extended key usage"
                        }
                    },
                    "required": ["validity_days"]
                }
            },
            {
                "name": "check_certificate_expiry",
                "description": "Check if a certificate is expiring soon or has expired.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "not_valid_after": {
                            "type": "string",
                            "description": "Certificate expiry date (ISO format)"
                        }
                    },
                    "required": ["not_valid_after"]
                }
            },
            {
                "name": "get_policy",
                "description": "Retrieve current cryptographic policies.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "policy_category": {
                            "type": "string",
                            "enum": ["key_generation", "certificate", "naming", "lifecycle", "all"],
                            "description": "Policy category to retrieve"
                        }
                    }
                }
            },
            {
                "name": "list_violations",
                "description": "List policy violations that have been recorded.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of violations to return"
                        }
                    }
                }
            },
            {
                "name": "compliance_report",
                "description": "Generate a compliance report for cryptographic operations.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "include_violations": {
                            "type": "boolean",
                            "description": "Include violation details in report"
                        }
                    }
                }
            }
        ]
    
    def _record_violation(self, violation_type: str, details: dict):
        """Record a policy violation"""
        violation = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": violation_type,
            "details": details
        }
        self.violations.append(violation)
    
    def validate_key_policy(self, algorithm: str, key_size: int = None, 
                           curve: str = None) -> dict:
        """Validate key generation parameters"""
        violations = []
        warnings = []
        
        key_policy = self.policies["key_generation"]
        
        # Validate algorithm
        if algorithm not in key_policy["allowed_algorithms"]:
            violations.append(
                f"Algorithm '{algorithm}' not allowed. "
                f"Allowed: {key_policy['allowed_algorithms']}"
            )
        
        # Validate RSA parameters
        if algorithm == "RSA":
            if key_size is None:
                warnings.append("Key size not specified, will use default (2048)")
            elif key_size < key_policy["rsa_min_key_size"]:
                violations.append(
                    f"RSA key size {key_size} below minimum "
                    f"{key_policy['rsa_min_key_size']}"
                )
            elif key_size not in key_policy["rsa_allowed_sizes"]:
                violations.append(
                    f"RSA key size {key_size} not in allowed sizes: "
                    f"{key_policy['rsa_allowed_sizes']}"
                )
        
        # Validate ECC parameters
        if algorithm == "ECC":
            if curve is None:
                warnings.append("Curve not specified, will use default (SECP256R1)")
            elif curve not in key_policy["ecc_allowed_curves"]:
                violations.append(
                    f"ECC curve '{curve}' not allowed. "
                    f"Allowed: {key_policy['ecc_allowed_curves']}"
                )
        
        # Record violations
        if violations:
            self._record_violation("key_generation", {
                "algorithm": algorithm,
                "key_size": key_size,
                "curve": curve,
                "violations": violations
            })
        
        is_compliant = len(violations) == 0
        
        return {
            "success": True,
            "compliant": is_compliant,
            "violations": violations,
            "warnings": warnings,
            "message": "Compliant with policy" if is_compliant else "Policy violations found"
        }
    
    def validate_certificate_policy(self, validity_days: int, 
                                   common_name: str = None,
                                   organization: str = None,
                                   country: str = None,
                                   key_usage: list = None,
                                   extended_key_usage: list = None) -> dict:
        """Validate certificate parameters"""
        violations = []
        warnings = []
        
        cert_policy = self.policies["certificate"]
        naming_policy = self.policies["naming"]
        
        # Validate validity period
        if validity_days > cert_policy["max_validity_days"]:
            violations.append(
                f"Validity period {validity_days} days exceeds maximum "
                f"{cert_policy['max_validity_days']} days"
            )
        
        if validity_days < cert_policy["min_validity_days"]:
            violations.append(
                f"Validity period {validity_days} days below minimum "
                f"{cert_policy['min_validity_days']} day(s)"
            )
        
        # Validate naming
        if naming_policy["require_organization"] and not organization:
            violations.append("Organization name is required by policy")
        
        if naming_policy["require_country"] and not country:
            violations.append("Country code is required by policy")
        
        if common_name and len(common_name) > naming_policy["max_common_name_length"]:
            violations.append(
                f"Common name length {len(common_name)} exceeds maximum "
                f"{naming_policy['max_common_name_length']}"
            )
        
        if naming_policy["allowed_countries"] and country:
            if country not in naming_policy["allowed_countries"]:
                violations.append(
                    f"Country '{country}' not in allowed list: "
                    f"{naming_policy['allowed_countries']}"
                )
        
        # Validate key usage
        if key_usage:
            invalid_ku = [ku for ku in key_usage 
                         if ku not in cert_policy["allowed_key_usages"]]
            if invalid_ku:
                violations.append(
                    f"Invalid key usages: {invalid_ku}. "
                    f"Allowed: {cert_policy['allowed_key_usages']}"
                )
        
        # Validate extended key usage
        if extended_key_usage:
            invalid_eku = [eku for eku in extended_key_usage 
                          if eku not in cert_policy["allowed_extended_key_usages"]]
            if invalid_eku:
                violations.append(
                    f"Invalid extended key usages: {invalid_eku}. "
                    f"Allowed: {cert_policy['allowed_extended_key_usages']}"
                )
        
        # Record violations
        if violations:
            self._record_violation("certificate", {
                "validity_days": validity_days,
                "common_name": common_name,
                "violations": violations
            })
        
        is_compliant = len(violations) == 0
        
        return {
            "success": True,
            "compliant": is_compliant,
            "violations": violations,
            "warnings": warnings,
            "message": "Compliant with policy" if is_compliant else "Policy violations found"
        }
    
    def check_certificate_expiry(self, not_valid_after: str) -> dict:
        """Check certificate expiry status"""
        try:
            expiry_date = datetime.fromisoformat(not_valid_after.replace('Z', '+00:00'))
            now = datetime.utcnow()
            
            days_until_expiry = (expiry_date - now).days
            
            warning_days = self.policies["lifecycle"]["renewal_warning_days"]
            
            status = "valid"
            needs_renewal = False
            
            if days_until_expiry < 0:
                status = "expired"
            elif days_until_expiry <= warning_days:
                status = "expiring_soon"
                needs_renewal = True
            
            return {
                "success": True,
                "status": status,
                "days_until_expiry": days_until_expiry,
                "expiry_date": not_valid_after,
                "needs_renewal": needs_renewal,
                "message": f"Certificate {status} ({days_until_expiry} days remaining)"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Expiry check failed: {str(e)}"
            }
    
    def get_policy(self, policy_category: str = "all") -> dict:
        """Get policy information"""
        if policy_category == "all":
            return {
                "success": True,
                "policies": self.policies,
                "message": "Retrieved all policies"
            }
        elif policy_category in self.policies:
            return {
                "success": True,
                "category": policy_category,
                "policy": self.policies[policy_category],
                "message": f"Retrieved {policy_category} policy"
            }
        else:
            return {
                "success": False,
                "error": f"Policy category '{policy_category}' not found"
            }
    
    def list_violations(self, limit: int = 10) -> dict:
        """List policy violations"""
        recent_violations = self.violations[-limit:] if limit else self.violations
        
        return {
            "success": True,
            "total_violations": len(self.violations),
            "violations": recent_violations,
            "message": f"Retrieved {len(recent_violations)} violations"
        }
    
    def compliance_report(self, include_violations: bool = True) -> dict:
        """Generate compliance report"""
        total_violations = len(self.violations)
        
        violation_by_type = {}
        for violation in self.violations:
            v_type = violation["type"]
            violation_by_type[v_type] = violation_by_type.get(v_type, 0) + 1
        
        report = {
            "success": True,
            "generated_at": datetime.utcnow().isoformat(),
            "total_violations": total_violations,
            "violations_by_type": violation_by_type,
            "compliance_status": "COMPLIANT" if total_violations == 0 else "NON-COMPLIANT",
            "policies_enforced": list(self.policies.keys())
        }
        
        if include_violations and total_violations > 0:
            report["recent_violations"] = self.violations[-10:]
        
        return report
