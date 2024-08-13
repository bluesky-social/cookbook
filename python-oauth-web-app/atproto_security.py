from urllib.parse import urlparse
import requests_hardened


# this is a crude/partial filter that looks at HTTPS URLs and checks if they seem "safe" for server-side requests (SSRF). This is only a partial mitigation, the actual HTTP client also needs to prevent other attacks and behaviors.
# this isn't a fully complete or secure implementation
def is_safe_url(url):
    parts = urlparse(url)
    if not (
        parts.scheme == "https"
        and parts.hostname is not None
        and parts.hostname == parts.netloc
        and parts.username is None
        and parts.password is None
        and parts.port is None
    ):
        return False

    segments = parts.hostname.split(".")
    if not (
        len(segments) >= 2
        and segments[-1] not in ["local", "arpa", "internal", "localhost"]
    ):
        return False

    if segments[-1].isdigit():
        return False

    return True


# configures a "hardened" requests wrapper
hardened_http = requests_hardened.Manager(
    requests_hardened.Config(
        default_timeout=(2, 10),
        never_redirect=True,
        ip_filter_enable=True,
        ip_filter_allow_loopback_ips=False,
        user_agent_override="AtprotoCookbookOAuthFlaskDemo",
    )
)
