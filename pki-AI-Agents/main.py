from orchestrator import run_certificate_flow

request = {
    "cn": "api.example.com",
    "algorithm": "RSA",
    "key_bits": 4096,
    "validity_days": 90,
    "eku": "serverAuth"
}

cert = run_certificate_flow(request)
print("\nFINAL RESULT:", cert)
