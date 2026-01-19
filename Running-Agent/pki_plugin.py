"""
PKI Operations MCP Plugin
Handles certificate operations, CA interactions, certificate lifecycle
"""

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from datetime import datetime, timedelta
import json

class PKIMCPPlugin:
    """MCP Plugin for PKI and certificate operations"""
    
    def __init__(self):
        self.certificates = {}
        self.ca_key = None
        self.ca_cert = None
        self._initialize_demo_ca()
        self.operation_log = []
    
    def _initialize_demo_ca(self):
        """Initialize a demo CA for testing (not for production use)"""
        # Generate CA private key
        self.ca_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=4096
        )
        
        # Create CA certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(x509.oid.NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(x509.oid.NameOID.STATE_OR_PROVINCE_NAME, "Demo State"),
            x509.NameAttribute(x509.oid.NameOID.LOCALITY_NAME, "Demo City"),
            x509.NameAttribute(x509.oid.NameOID.ORGANIZATION_NAME, "Demo CA Organization"),
            x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "Demo Root CA"),
        ])
        
        self.ca_cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            self.ca_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=3650)
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True
        ).add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False
            ),
            critical=True
        ).sign(self.ca_key, hashes.SHA256())
    
    def get_tools(self):
        """Return MCP tool definitions"""
        return [
            {
                "name": "issue_certificate",
                "description": "Issue an X.509 certificate from a CSR using the demo CA.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "csr_pem": {
                            "type": "string",
                            "description": "Certificate Signing Request in PEM format"
                        },
                        "validity_days": {
                            "type": "integer",
                            "description": "Certificate validity period in days",
                            "default": 365
                        },
                        "cert_id": {
                            "type": "string",
                            "description": "Unique identifier for this certificate"
                        },
                        "key_usage": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key usage extensions (digitalSignature, keyEncipherment, etc.)"
                        },
                        "extended_key_usage": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Extended key usage (serverAuth, clientAuth, etc.)"
                        }
                    },
                    "required": ["csr_pem", "cert_id"]
                }
            },
            {
                "name": "revoke_certificate",
                "description": "Revoke an issued certificate.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "cert_id": {
                            "type": "string",
                            "description": "Certificate identifier to revoke"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Revocation reason"
                        }
                    },
                    "required": ["cert_id"]
                }
            },
            {
                "name": "renew_certificate",
                "description": "Renew an existing certificate with extended validity.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "cert_id": {
                            "type": "string",
                            "description": "Certificate identifier to renew"
                        },
                        "validity_days": {
                            "type": "integer",
                            "description": "New validity period in days"
                        }
                    },
                    "required": ["cert_id"]
                }
            },
            {
                "name": "get_certificate",
                "description": "Retrieve certificate information and PEM.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "cert_id": {
                            "type": "string",
                            "description": "Certificate identifier"
                        }
                    },
                    "required": ["cert_id"]
                }
            },
            {
                "name": "list_certificates",
                "description": "List all certificates in the inventory.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["active", "revoked", "expired", "all"],
                            "description": "Filter certificates by status"
                        }
                    }
                }
            },
            {
                "name": "get_ca_certificate",
                "description": "Get the demo CA certificate.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
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
    
    def issue_certificate(self, csr_pem: str, cert_id: str, 
                         validity_days: int = 365,
                         key_usage: list = None,
                         extended_key_usage: list = None) -> dict:
        """Issue a certificate from a CSR"""
        try:
            # Load CSR
            csr = x509.load_pem_x509_csr(csr_pem.encode('utf-8'))
            
            # Verify CSR signature
            if not csr.is_signature_valid:
                return {
                    "success": False,
                    "error": "CSR signature is invalid"
                }
            
            # Build certificate
            cert_builder = x509.CertificateBuilder().subject_name(
                csr.subject
            ).issuer_name(
                self.ca_cert.subject
            ).public_key(
                csr.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=validity_days)
            )
            
            # Add Basic Constraints
            cert_builder = cert_builder.add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True
            )
            
            # Add Key Usage if specified
            if key_usage:
                ku_dict = {
                    "digital_signature": "digitalSignature" in key_usage,
                    "key_encipherment": "keyEncipherment" in key_usage,
                    "content_commitment": "contentCommitment" in key_usage,
                    "data_encipherment": "dataEncipherment" in key_usage,
                    "key_agreement": "keyAgreement" in key_usage,
                    "key_cert_sign": "keyCertSign" in key_usage,
                    "crl_sign": "cRLSign" in key_usage,
                    "encipher_only": False,
                    "decipher_only": False
                }
                cert_builder = cert_builder.add_extension(
                    x509.KeyUsage(**ku_dict),
                    critical=True
                )
            else:
                # Default key usage for server certificates
                cert_builder = cert_builder.add_extension(
                    x509.KeyUsage(
                        digital_signature=True,
                        key_encipherment=True,
                        content_commitment=False,
                        data_encipherment=False,
                        key_agreement=False,
                        key_cert_sign=False,
                        crl_sign=False,
                        encipher_only=False,
                        decipher_only=False
                    ),
                    critical=True
                )
            
            # Add Extended Key Usage if specified
            if extended_key_usage:
                eku_map = {
                    "serverAuth": x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                    "clientAuth": x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
                    "codeSigning": x509.oid.ExtendedKeyUsageOID.CODE_SIGNING,
                    "emailProtection": x509.oid.ExtendedKeyUsageOID.EMAIL_PROTECTION
                }
                eku_list = [eku_map[eku] for eku in extended_key_usage if eku in eku_map]
                if eku_list:
                    cert_builder = cert_builder.add_extension(
                        x509.ExtendedKeyUsage(eku_list),
                        critical=False
                    )
            
            # Copy SAN from CSR if present
            try:
                san_ext = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName)
                cert_builder = cert_builder.add_extension(san_ext.value, critical=False)
            except x509.ExtensionNotFound:
                pass
            
            # Sign certificate
            certificate = cert_builder.sign(self.ca_key, hashes.SHA256())
            
            # Store certificate
            self.certificates[cert_id] = {
                "certificate": certificate,
                "status": "active",
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": certificate.not_valid_after_utc.isoformat(),
                "subject": certificate.subject.rfc4514_string()
            }
            
            # Get certificate PEM
            cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            
            self._log_operation("issue_certificate", {
                "cert_id": cert_id,
                "subject": certificate.subject.rfc4514_string(),
                "validity_days": validity_days
            })
            
            return {
                "success": True,
                "cert_id": cert_id,
                "serial_number": str(certificate.serial_number),
                "subject": certificate.subject.rfc4514_string(),
                "issuer": certificate.issuer.rfc4514_string(),
                "not_valid_before": certificate.not_valid_before_utc.isoformat(),
                "not_valid_after": certificate.not_valid_after_utc.isoformat(),
                "certificate_pem": cert_pem,
                "message": "Certificate issued successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Certificate issuance failed: {str(e)}"
            }
    
    def revoke_certificate(self, cert_id: str, reason: str = "unspecified") -> dict:
        """Revoke a certificate"""
        try:
            if cert_id not in self.certificates:
                return {
                    "success": False,
                    "error": f"Certificate '{cert_id}' not found"
                }
            
            cert_data = self.certificates[cert_id]
            
            if cert_data["status"] == "revoked":
                return {
                    "success": False,
                    "error": "Certificate is already revoked"
                }
            
            cert_data["status"] = "revoked"
            cert_data["revoked_at"] = datetime.utcnow().isoformat()
            cert_data["revocation_reason"] = reason
            
            self._log_operation("revoke_certificate", {
                "cert_id": cert_id,
                "reason": reason
            })
            
            return {
                "success": True,
                "cert_id": cert_id,
                "status": "revoked",
                "revoked_at": cert_data["revoked_at"],
                "reason": reason,
                "message": "Certificate revoked successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Certificate revocation failed: {str(e)}"
            }
    
    def renew_certificate(self, cert_id: str, validity_days: int = 365) -> dict:
        """Renew a certificate"""
        try:
            if cert_id not in self.certificates:
                return {
                    "success": False,
                    "error": f"Certificate '{cert_id}' not found"
                }
            
            old_cert_data = self.certificates[cert_id]
            old_cert = old_cert_data["certificate"]
            
            # Create renewed certificate
            new_cert = x509.CertificateBuilder().subject_name(
                old_cert.subject
            ).issuer_name(
                self.ca_cert.subject
            ).public_key(
                old_cert.public_key()
            ).serial_number(
                x509.random_serial_number()
            ).not_valid_before(
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=validity_days)
            )
            
            # Copy extensions
            for ext in old_cert.extensions:
                new_cert = new_cert.add_extension(ext.value, critical=ext.critical)
            
            # Sign new certificate
            renewed_cert = new_cert.sign(self.ca_key, hashes.SHA256())
            
            # Update certificate data
            new_cert_id = f"{cert_id}_renewed"
            self.certificates[new_cert_id] = {
                "certificate": renewed_cert,
                "status": "active",
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": renewed_cert.not_valid_after_utc.isoformat(),
                "subject": renewed_cert.subject.rfc4514_string(),
                "renewed_from": cert_id
            }
            
            # Mark old certificate as superseded
            old_cert_data["status"] = "superseded"
            old_cert_data["superseded_by"] = new_cert_id
            
            cert_pem = renewed_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
            
            self._log_operation("renew_certificate", {
                "old_cert_id": cert_id,
                "new_cert_id": new_cert_id,
                "validity_days": validity_days
            })
            
            return {
                "success": True,
                "old_cert_id": cert_id,
                "new_cert_id": new_cert_id,
                "serial_number": str(renewed_cert.serial_number),
                "not_valid_after": renewed_cert.not_valid_after_utc.isoformat(),
                "certificate_pem": cert_pem,
                "message": "Certificate renewed successfully"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Certificate renewal failed: {str(e)}"
            }
    
    def get_certificate(self, cert_id: str) -> dict:
        """Get certificate information"""
        if cert_id not in self.certificates:
            return {
                "success": False,
                "error": f"Certificate '{cert_id}' not found"
            }
        
        cert_data = self.certificates[cert_id]
        cert = cert_data["certificate"]
        
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        
        return {
            "success": True,
            "cert_id": cert_id,
            "serial_number": str(cert.serial_number),
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "status": cert_data["status"],
            "issued_at": cert_data["issued_at"],
            "expires_at": cert_data["expires_at"],
            "certificate_pem": cert_pem
        }
    
    def list_certificates(self, status: str = "all") -> dict:
        """List certificates"""
        filtered_certs = []
        
        for cert_id, cert_data in self.certificates.items():
            if status == "all" or cert_data["status"] == status:
                filtered_certs.append({
                    "cert_id": cert_id,
                    "subject": cert_data["subject"],
                    "status": cert_data["status"],
                    "issued_at": cert_data["issued_at"],
                    "expires_at": cert_data["expires_at"]
                })
        
        return {
            "success": True,
            "total_certificates": len(filtered_certs),
            "certificates": filtered_certs,
            "message": f"Retrieved {len(filtered_certs)} certificates"
        }
    
    def get_ca_certificate(self) -> dict:
        """Get CA certificate"""
        ca_pem = self.ca_cert.public_bytes(serialization.Encoding.PEM).decode('utf-8')
        
        return {
            "success": True,
            "subject": self.ca_cert.subject.rfc4514_string(),
            "serial_number": str(self.ca_cert.serial_number),
            "not_valid_before": self.ca_cert.not_valid_before_utc.isoformat(),
            "not_valid_after": self.ca_cert.not_valid_after_utc.isoformat(),
            "certificate_pem": ca_pem,
            "message": "This is a DEMO CA for testing only - not for production use"
        }
