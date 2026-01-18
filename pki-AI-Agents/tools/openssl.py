def create_csr(name, key_ref):
    print(f"[OpenSSL] Creating CSR for {name} using {key_ref}")
    return f"CSR({name})"
