"""
Cryptographic Operations MCP Plugin
Handles key generation, CSR creation using standard cryptographic libraries
"""

from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta
import json

class CryptoMCPPlugin:
    """MCP Plugin for cryptographic operations"""
    
    def __init__(self):
        self.key_store = {}  # In-memory key storage for demo
        self.csr_store = {}
        self.operation_log = []
    
    def get_tools(self):
        """Return MCP tool definitions"""
        return [
            {
                "name": "generate_key_pair",
                "description": "Generate an asymmetric key pair (RSA or ECC) using approved parameters. Never perform manual key generation - always use this tool.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "algorithm": {
                            "type": "string",
                            "enum": ["RSA", "ECC"],
                            "description": "Key algorithm type"
                        },
                        "key_size": {
                            "type": "integer",
                            "enum": [2048, 3072, 4096],
                            "description": "Key size in bits (for RSA)"
                        },
                        "curve": {
                            "type": "string",
                            "enum": ["SECP256R1", "SECP384R1", "SECP521R1"],
                            "description": "Elliptic curve name (for ECC)"
                        },
                        "key_id": {
                            "type": "string",
                            "description": "Unique identifier for this key pair"
                        }
                    },
                    "required": ["algorithm", "key_id"]
                }
            },
            {
                "name": "create_csr",
                "description": "Create a Certificate Signing Request (CSR) for a previously generated key pair.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key_id": {
                            "type": "string",
                            "description": "Key pair identifier to use for CSR"
                        },
                        "common_name": {
                            "type": "string",
                            "description": "Common Name (CN) for the certificate"
                        },
                        "organization": {
                            "type": "string",
                            "description": "Organization (O)"
                        },
                        "organizational_unit": {
                            "type": "string",
                            "description": "Organizational Unit (OU)"
                        },
                        "country": {
                            "type": "string",
                            "description": "Country (C) - two letter code"
                        },
                        "state": {
                            "type": "string",
                            "description": "State or Province (ST)"
                        },
                        "locality": {
                            "type": "string",
                            "description": "Locality or City (L)"
                        },
                        "san_dns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Subject Alternative Names (DNS)"
                        }
                    },
                    "required": ["key_id", "common_name"]
                }
            },
            {
                "name": "validate_csr",
                "description": "Validate a Certificate Signing Request for correctness and compliance.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "csr_id": {
                            "type": "string",
                            "description": "CSR identifier to validate"
                        }
                    },
                    "required": ["csr_id"]
                }
            },
            {
                "name": "get_key_info",
                "description": "Retrieve information about a generated key pair.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "key_id": {
                            "type": "string",
                            "description": "Key pair identifier"
                        }
                    },
                    "required": ["key_id"]
                }
            },
            {
                "name": "list_operations",
                "description": "List all cryptographic operations performed (audit log).",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of operations to return"
                        }
                    }
                }
            }
        ]
    
    def _log_operation(self, operation: str, details: dict):
        """Log an operation for audit purposes"""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "details": details
        }
        self.operation_log.append(log_entry)
    
    def generate_key_pair(self, algorithm: str, key_id: str, 
                         key_size: int = None, curve: str = None) -> dict:
        """Generate asymmetric key pair"""
        try:
            if algorithm == "RSA":
                if not key_size:
                    key_size = 2048
                
                if key_size not in [2048, 3072, 4096]:
                    return {
                        "success": False,
                        "error": f"Invalid RSA key size: {key_size}. Must be 2048, 3072, or 4096."
                    }
                
                # Generate RSA key pair
                private_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=key_size
                )
                
                key_info = {
                    "algorithm": "RSA",
                    "key_size": key_size,
                    "public_exponent": 65537
                }
                
            elif algorithm == "ECC":
                if not curve:
                    curve = "SECP256R1"
                
                curve_map = {
                    "SECP256R1": ec.SECP256R1(),
                    "SECP384R1": ec.SECP384R1(),
                    "SECP521R1": ec.SECP521R1()
                }
                
                if curve not in curve_map:
                    return {
                        "success": False,
                        "error": f"Invalid ECC curve: {curve}"
                    }
                
                # Generate ECC key pair
                private_key = ec.generate_private_key(curve_map[curve])
                
                key_info = {
                    "algorithm": "ECC",
                    "curve": curve
                }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported algorithm: {algorithm}"
                }
            
            # Store the key pair
            self.key_store[key_id] = {
                "private_key": private_key,
                "public_key": private_key.public_key(),
                "info": key_info,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Get public key PEM
            public_pem = private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ).decode('utf-8')
            
            self._log_operation("generate_key_pair", {
                "key_id": key_id,
                "algorithm": algorithm,
                **key_info
            })
            
            return {
                "success": True,
                "key_id": key_id,
                "algorithm": algorithm,
                "key_info": key_info,
                "public_key_pem": public_pem,
                "message": f"{algorithm} key pair generated successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Key generation failed: {str(e)}"
            }
    
    def create_csr(self, key_id: str, common_name: str, 
                   organization: str = None, organizational_unit: str = None,
                   country: str = None, state: str = None, 
                   locality: str = None, san_dns: list = None) -> dict:
        """Create Certificate Signing Request"""
        try:
            if key_id not in self.key_store:
                return {
                    "success": False,
                    "error": f"Key ID '{key_id}' not found. Generate key pair first."
                }
            
            private_key = self.key_store[key_id]["private_key"]
            
            # Build subject name
            name_attributes = [
                x509.NameAttribute(NameOID.COMMON_NAME, common_name)
            ]
            
            if organization:
                name_attributes.append(
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization)
                )
            if organizational_unit:
                name_attributes.append(
                    x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, organizational_unit)
                )
            if country:
                name_attributes.append(
                    x509.NameAttribute(NameOID.COUNTRY_NAME, country)
                )
            if state:
                name_attributes.append(
                    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state)
                )
            if locality:
                name_attributes.append(
                    x509.NameAttribute(NameOID.LOCALITY_NAME, locality)
                )
            
            # Build CSR
            csr_builder = x509.CertificateSigningRequestBuilder().subject_name(
                x509.Name(name_attributes)
            )
            
            # Add SAN if provided
            if san_dns:
                san_list = [x509.DNSName(dns) for dns in san_dns]
                csr_builder = csr_builder.add_extension(
                    x509.SubjectAlternativeName(san_list),
                    critical=False
                )
            
            # Sign CSR with private key
            csr = csr_builder.sign(private_key, hashes.SHA256())
            
            # Store CSR
            csr_id = f"csr_{key_id}"
            self.csr_store[csr_id] = {
                "csr": csr,
                "key_id": key_id,
                "subject": common_name,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Get CSR PEM
            csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            
            self._log_operation("create_csr", {
                "csr_id": csr_id,
                "key_id": key_id,
                "common_name": common_name,
                "organization": organization
            })
            
            return {
                "success": True,
                "csr_id": csr_id,
                "key_id": key_id,
                "subject": common_name,
                "csr_pem": csr_pem,
                "message": "CSR created successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"CSR creation failed: {str(e)}"
            }
    
    def validate_csr(self, csr_id: str) -> dict:
        """Validate a CSR"""
        try:
            if csr_id not in self.csr_store:
                return {
                    "success": False,
                    "error": f"CSR ID '{csr_id}' not found"
                }
            
            csr_data = self.csr_store[csr_id]
            csr = csr_data["csr"]
            
            # Verify signature
            is_valid = csr.is_signature_valid
            
            # Extract subject info
            subject_info = {}
            for attribute in csr.subject:
                subject_info[attribute.oid._name] = attribute.value
            
            self._log_operation("validate_csr", {
                "csr_id": csr_id,
                "is_valid": is_valid
            })
            
            return {
                "success": True,
                "csr_id": csr_id,
                "is_signature_valid": is_valid,
                "subject": subject_info,
                "public_key_algorithm": csr.public_key().__class__.__name__,
                "message": "CSR validation completed"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"CSR validation failed: {str(e)}"
            }
    
    def get_key_info(self, key_id: str) -> dict:
        """Get information about a key pair"""
        if key_id not in self.key_store:
            return {
                "success": False,
                "error": f"Key ID '{key_id}' not found"
            }
        
        key_data = self.key_store[key_id]
        
        return {
            "success": True,
            "key_id": key_id,
            "info": key_data["info"],
            "created_at": key_data["created_at"],
            "has_csr": f"csr_{key_id}" in self.csr_store
        }
    
    def list_operations(self, limit: int = 10) -> dict:
        """List recent operations"""
        recent_ops = self.operation_log[-limit:] if limit else self.operation_log
        
        return {
            "success": True,
            "total_operations": len(self.operation_log),
            "operations": recent_ops,
            "message": f"Retrieved {len(recent_ops)} operations"
        }
