import re
import sys
import json
import requests
import dns.resolver

from atproto_security import is_safe_url, hardened_http

HANDLE_REGEX = r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
DID_REGEX = r"^did:[a-z]+:[a-zA-Z0-9._:%-]*[a-zA-Z0-9._-]$"


def valid_handle(handle):
    return re.match(HANDLE_REGEX, handle) != None


def valid_did(did):
    return re.match(DID_REGEX, did) != None


def resolve_handle(handle):
    # first try TXT record
    try:
        for record in dns.resolver.resolve(f"_atproto.{handle}", "TXT"):
            val = record.to_text().replace('"', "")
            if val.startswith("did="):
                val = val[4:]
                if valid_did(val):
                    return val
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
        pass

    # then try HTTP well-known
    # IMPORTANT: 'handle' domain is untrusted user input. SSRF mitigations are necessary
    try:
        with hardened_http.get_session() as sess:
            resp = sess.get(f"https://{handle}/.well-known/atproto-did")
    except requests.exceptions.ConnectionError:
        return None
    if resp.status_code != 200:
        return None
    did = resp.text.split()[0]
    if valid_did(did):
        return did
    return None


def resolve_did(did):
    if did.startswith("did:plc:"):
        # NOTE: 'did' is untrusted input, but has been validated by regex by this point
        resp = requests.get(f"https://plc.directory/{did}")
        if resp.status_code != 200:
            return None
        return resp.json()

    if did.startswith("did:web:"):
        domain = did[8:]
        # IMPORTANT: domain is untrusted input. SSRF mitigations are necessary
        # "handle" validation works to check that domain is a simple hostname
        assert valid_handle(domain)
        try:
            with hardened_http.get_session() as sess:
                resp = sess.get(f"https://{domain}/.well-known/did.json")
        except requests.exceptions.ConnectionError:
            return None
        if resp.status_code != 200:
            return None
        return resp.json()


def pds_endpoint(doc):
    for svc in doc["service"]:
        if svc["id"] == "#atproto_pds":
            return svc["serviceEndpoint"]
    raise Exception("PDS endpoint not found in DID document")


if __name__ == "__main__":
    assert valid_did("did:web:example.com")
    assert valid_did("did:plc:abc123")
    assert valid_did("") == False
    assert valid_did("did:asdfasdf") == False
    handle = sys.argv[1]
    if not valid_handle(handle):
        print("invalid handle!")
        sys.exit(-1)
    did = resolve_handle(handle)
    print(f"DID: {did}")
    doc = resolve_did(did)
    print(doc)
