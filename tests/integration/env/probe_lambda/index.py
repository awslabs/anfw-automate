"""Probe Lambda — TCP reachability check from within the tenant VPC.

Deployed inside the tenant VPC (TGW-attached, routed through NFW).
Accepts a domain:port and attempts a TCP socket connect to determine
if Network Firewall rules allow or block the traffic.

Invocation payload:
    {"domain": "example.com", "port": 443, "timeout_s": 10}

Response:
    {"reachable": true/false, "error": null/"message"}
"""

import json
import socket


def handler(event, context):
    """Attempt TCP connect and return reachability result."""
    domain = event.get("domain", "")
    port = int(event.get("port", 443))
    timeout_s = float(event.get("timeout_s", 10))

    if not domain:
        return {
            "reachable": False,
            "error": "Missing 'domain' in event payload",
        }

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_s)
        result = sock.connect_ex((domain, port))
        sock.close()

        reachable = result == 0
        return {
            "reachable": reachable,
            "error": None if reachable else f"connect_ex returned {result}",
        }
    except socket.timeout:
        return {
            "reachable": False,
            "error": f"Connection timed out after {timeout_s}s",
        }
    except socket.gaierror as e:
        return {
            "reachable": False,
            "error": f"DNS resolution failed: {e}",
        }
    except Exception as e:
        return {
            "reachable": False,
            "error": str(e),
        }
