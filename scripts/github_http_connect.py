#!/usr/bin/env python3
"""Forward OpenSSH stdio over the user-scoped Mihomo HTTP CONNECT proxy."""
import base64
import os
import socket
import sys
import threading
from urllib.parse import unquote, urlsplit


def fail(message):
    print(f"github-proxy: {message}", file=sys.stderr)
    sys.exit(1)


def write_all(data):
    pending = memoryview(data)
    while pending:
        pending = pending[os.write(1, pending):]


def main():
    if len(sys.argv) != 3:
        fail("expected destination host and port")
    host, port = sys.argv[1], int(sys.argv[2])
    proxy = urlsplit(os.environ.get("https_proxy") or os.environ.get("HTTPS_PROXY") or "")
    if proxy.scheme != "http" or not proxy.hostname:
        fail("source ~/.config/mihomo/proxy.env before ssh/git")
    target = f"{host}:{port}"
    headers = [f"CONNECT {target} HTTP/1.1", f"Host: {target}", "Proxy-Connection: Keep-Alive"]
    if proxy.username is not None:
        credentials = f"{unquote(proxy.username)}:{unquote(proxy.password or '')}".encode()
        headers.append("Proxy-Authorization: Basic " + base64.b64encode(credentials).decode())
    request = ("\r\n".join(headers) + "\r\n\r\n").encode()
    try:
        with socket.create_connection((proxy.hostname, proxy.port or 80), timeout=15) as sock:
            sock.sendall(request)
            response = b""
            while b"\r\n\r\n" not in response:
                chunk = sock.recv(4096)
                if not chunk or len(response) + len(chunk) > 65536:
                    fail("proxy closed connection during CONNECT")
                response += chunk
            header, _, remainder = response.partition(b"\r\n\r\n")
            status = header.split(b"\r\n", 1)[0]
            if len(status.split()) < 2 or status.split()[1] != b"200":
                fail("HTTP CONNECT rejected: " + status.decode(errors="replace"))
            sock.settimeout(None)
            if remainder:
                write_all(remainder)

            def feed_socket():
                try:
                    while True:
                        data = os.read(0, 65536)
                        if not data:
                            break
                        sock.sendall(data)
                except OSError:
                    pass
                try:
                    sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass

            threading.Thread(target=feed_socket, daemon=True).start()
            while True:
                data = sock.recv(65536)
                if not data:
                    break
                write_all(data)
    except (OSError, ValueError) as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
