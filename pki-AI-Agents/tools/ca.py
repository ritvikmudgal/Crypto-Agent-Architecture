def issue_certificate(csr):
    print(f"[CA] Issuing certificate for {csr}")
    return {"cn": csr.replace("CSR(", "").replace(")", ""), "serial": "ABC123"}
