import re
import sys
import requests
import dns.resolver
from typing import Optional, Tuple

from atproto_security import hardened_http

HANDLE_REGEX = r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
DID_REGEX = r"^did:[a-z]+:[a-zA-Z0-9._:%-]*[a-zA-Z0-9._-]$"


def is_valid_handle(handle: str) -> bool:
    return re.match(HANDLE_REGEX, handle) is not None


def is_valid_did(did: str) -> bool:
    return re.match(DID_REGEX, did) is not None


def handle_from_doc(doc: dict) -> Optional[str]:
    for aka in doc.get("alsoKnownAs", []):
        if aka.startswith("at://"):
            handle = aka[5:]
            if is_valid_handle(handle):
                return handle
    return None


# resolves an identity (handle or DID) to a DID, handle, and DID document. verifies handle bi-directionally.
def resolve_identity(atid: str) -> Tuple[str, str, dict]:
    if is_valid_handle(atid):
        handle = atid
        did = resolve_handle(handle)
        if not did:
            raise Exception("Failed to resolve handle: " + handle)
        doc = resolve_did(did)
        if not doc:
            raise Exception("Failed to resolve DID: " + did)
        doc_handle = handle_from_doc(doc)
        if not doc_handle or doc_handle != handle:
            raise Exception("Handle did not match DID: " + handle)
        return did, handle, doc
    if is_valid_did(atid):
        did = atid
        doc = resolve_did(did)
        if not doc:
            raise Exception("Failed to resolve DID: " + did)
        handle = handle_from_doc(doc)
        if not handle:
            raise Exception("Handle did not match DID: " + handle)
        if resolve_handle(handle) != did:
            raise Exception("Handle did not match DID: " + handle)
        return did, handle, doc

    raise Exception("identifier not a handle or DID: " + atid)


def resolve_handle(handle: str) -> Optional[str]:

    # first try TXT record
    try:
        for record in dns.resolver.resolve(f"_atproto.{handle}", "TXT"):
            val = record.to_text().replace('"', "")
            if val.startswith("did="):
                val = val[4:]
                if is_valid_did(val):
                    return val
    except Exception:
        pass

    # then try HTTP well-known
    # IMPORTANT: 'handle' domain is untrusted user input. SSRF mitigations are necessary
    try:
        with hardened_http.get_session() as sess:
            resp = sess.get(f"https://{handle}/.well-known/atproto-did")
    except Exception:
        return None

    if resp.status_code != 200:
        return None
    did = resp.text.split()[0]
    if is_valid_did(did):
        return did
    return None


def resolve_did(did: str) -> Optional[dict]:
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
        assert is_valid_handle(domain)
        try:
            with hardened_http.get_session() as sess:
                resp = sess.get(f"https://{domain}/.well-known/did.json")
        except requests.exceptions.ConnectionError:
            return None
        if resp.status_code != 200:
            return None
        return resp.json()
    raise ValueError("unsupported DID type")


def pds_endpoint(doc: dict) -> str:
    for svc in doc["service"]:
        if svc["id"] == "#atproto_pds":
            return svc["serviceEndpoint"]
    raise Exception("PDS endpoint not found in DID document")


if __name__ == "__main__":
    assert is_valid_did("did:web:example.com")
    assert is_valid_did("did:plc:abc123")
    assert is_valid_did("") is False
    assert is_valid_did("did:asdfasdf") is False
    handle = sys.argv[1]
    if not is_valid_handle(handle):
        print("invalid handle!")
        sys.exit(-1)
    assert handle is not None
    did = resolve_handle(handle)
    print(f"DID: {did}")
    assert did is not None
    doc = resolve_did(did)
    print(doc)
    resolve_identity(handle)
    resolve_identity(did)
