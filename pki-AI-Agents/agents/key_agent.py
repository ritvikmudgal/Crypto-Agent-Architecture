from tools.vault import create_key

def generate_key(common_name, key_bits):
    return create_key(common_name, key_bits)
