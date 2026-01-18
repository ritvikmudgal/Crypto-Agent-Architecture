def validate_request(req, policy):
    if req["algorithm"] not in policy["allowed_algorithms"]:
        return False, "Algorithm not allowed"

    if req["key_bits"] < policy["min_rsa_bits"]:
        return False, "Key size too weak"

    if req["validity_days"] > policy["max_cert_days"]:
        return False, "Validity too long"

    if req["eku"] not in policy["allowed_ekus"]:
        return False, "EKU not permitted"

    return True, "APPROVED"
