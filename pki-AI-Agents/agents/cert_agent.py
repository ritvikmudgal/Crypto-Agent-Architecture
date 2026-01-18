from tools.openssl import create_csr
from tools.ca import issue_certificate

def issue_cert(common_name, key_ref):
    csr = create_csr(common_name, key_ref)
    cert = issue_certificate(csr)
    return cert
