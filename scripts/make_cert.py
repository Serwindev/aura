"""Self-signed HTTPS certificate so a phone on the same Wi-Fi can use the microphone (browsers
only allow the mic on localhost or HTTPS). Demo only. Written to the git-ignored server/data/certs."""

from __future__ import annotations

import datetime as dt
import ipaddress
import socket
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

OUT = Path(__file__).resolve().parents[1] / "server" / "data" / "certs"


def lan_addresses() -> list[str]:
    found = {"127.0.0.1"}
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        found.add(info[4][0])
    try:  # the interface that holds the default route; no packet is actually sent
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            found.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(found)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AURA local demo")])
    addrs = lan_addresses()
    now = dt.datetime.now(dt.UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=60))
            .add_extension(x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), *(x509.IPAddress(ipaddress.ip_address(a)) for a in addrs)]), critical=False)
            .sign(key, hashes.SHA256()))
    (OUT / "key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                                                    serialization.NoEncryption()))
    (OUT / "cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    print("On the phone (same Wi-Fi), open:")
    for a in addrs:
        if a != "127.0.0.1":
            print(f"  https://{a}:8443")


if __name__ == "__main__":
    main()
