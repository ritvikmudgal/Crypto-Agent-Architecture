import json

from agents.policy_agent import validate_request
from agents.key_agent import generate_key
from agents.cert_agent import issue_cert
from agents.inventory_agent import store_certificate
from agents.audit_agent import log


def run_certificate_flow(request):
    policy = json.load(open("policies/policy.json"))

    log("REQUEST_RECEIVED", request)

    ok, reason = validate_request(request, policy)
    if not ok:
        log("POLICY_REJECTED", reason)
        raise Exception(reason)

    log("POLICY_APPROVED", reason)

    key_ref = generate_key(request["cn"], request["key_bits"])
    log("KEY_CREATED", key_ref)

    cert = issue_cert(request["cn"], key_ref)
    log("CERT_ISSUED", cert)

    store_certificate(cert)
    log("INVENTORY_UPDATED", cert["serial"])

    return cert
