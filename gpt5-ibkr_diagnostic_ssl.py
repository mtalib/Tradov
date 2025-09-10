import socket
import ssl
import os
import glob

# Build a minimal but valid IB API handshake string
def build_ib_handshake(client_id=1):
    min_version = 100
    max_version = 178
    return f"API\0v{min_version}..{max_version}\0{client_id}\0".encode()


def test_api_protocol_plain(host, port, client_id=1):
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.settimeout(5)
        handshake = build_ib_handshake(client_id)
        sock.sendall(handshake)
        try:
            data = sock.recv(1024)
            if data:
                return True, f"Plain API response: {data[:100]!r}"
            else:
                return True, "Plain connected but no response after handshake."
        except socket.timeout:
            return True, "Plain connected but API handshake timed out."
    except Exception as e:
        return False, f"Plain connection failed: {e}"


def test_api_protocol_tls(host, port, client_id=1):
    try:
        raw_sock = socket.create_connection((host, port), timeout=5)
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(raw_sock, server_hostname=host) as ssock:
            ssock.settimeout(5)
            handshake = build_ib_handshake(client_id)
            ssock.sendall(handshake)
            try:
                data = ssock.recv(1024)
                if data:
                    return True, f"TLS API response: {data[:100]!r}"
                else:
                    return True, "TLS connected but no response after handshake."
            except socket.timeout:
                return True, "TLS connected but API handshake timed out."
    except Exception as e:
        return False, f"TLS connection failed: {e}"


def find_gateway_logs():
    search_dirs = ["~/Jts", "~/.ibgateway"]
    candidates = []
    for d in search_dirs:
        d = os.path.expanduser(d)
        for path in glob.glob(os.path.join(d, "**/ibgateway.log"), recursive=True):
            candidates.append(path)
    return candidates


def check_gateway_logs():
    logs = find_gateway_logs()
    if not logs:
        return "No ibgateway.log files found under ~/Jts or ~/.ibgateway."

    latest_log = max(logs, key=os.path.getmtime)
    try:
        with open(latest_log, "r", errors="ignore") as f:
            lines = f.readlines()[-200:]
        api_lines = [ln for ln in lines if "API" in ln or "socket" in ln]
        if api_lines:
            return f"Latest log file: {latest_log}\nRecent API log activity:\n" + "\n".join(api_lines[-10:])
        else:
            return f"Latest log file: {latest_log}\nNo recent API-related entries in ibgateway.log."
    except Exception as e:
        return f"Could not read log file {latest_log}: {e}"


def diagnose_ib_api(host="127.0.0.1", port=4002, client_id=1):
    print(f"\n--- Testing IB API on {host}:{port} ---")

    plain_ok, plain_msg = test_api_protocol_plain(host, port, client_id)
    print("[Plain]", plain_msg)

    tls_ok, tls_msg = test_api_protocol_tls(host, port, client_id)
    print("[TLS]  ", tls_msg)

    if tls_ok and not plain_ok:
        print("Result: This API port requires TLS (Use SSL sockets = ON).")
    elif plain_ok and not tls_ok:
        print("Result: This API port is plain-text only (Use SSL sockets = OFF).")
    elif plain_ok and tls_ok:
        print("Result: Both plain and TLS connect (unexpected; check Gateway version).")
    else:
        print("Result: Could not connect using either plain or TLS (check if Gateway is running, logged in, and port is correct).")

    # Check Gateway logs for evidence of API connections
    print("\n--- Checking Gateway Logs ---")
    log_report = check_gateway_logs()
    print(log_report)


if __name__ == "__main__":
    diagnose_ib_api(host="127.0.0.1", port=4002, client_id=123)
