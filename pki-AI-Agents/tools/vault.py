def create_key(name, bits):
    print(f"[Vault] Generating RSA-{bits} key for {name}")
    return f"vault:key:{name}"
