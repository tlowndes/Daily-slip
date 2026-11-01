#!/usr/bin/env python3
"""Daily Slip helper.

Runs on your PC. It serves the Daily Slip page at http://localhost:8765,
reads your weekly note from your Obsidian vault, and sends the finished
receipt to an Ethernet ESC/POS printer on port 9100. Python 3.8+, no extra packages.
"""
import base64, json, os, re, socket, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
CONFIG_FILE = HERE / "config.json"
PORT = int(os.environ.get("DAILY_SLIP_PORT", "8765"))
DEFAULTS = {
    "printer_ip": "",
    "printer_port": 9100,
    "cut": True,
    "vault_path": "",
    "weekly_note": "01 - Inbox/Weekly Shop.md",
}
HOST_OK = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}
print_lock = threading.Lock()


def load_config():
    cfg = dict(DEFAULTS)
    try:
        cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(new):
    cfg = load_config()
    ip = str(new.get("printer_ip", cfg["printer_ip"])).strip()
    if ip and not re.fullmatch(r"[A-Za-z0-9.\-]{1,253}", ip):
        raise ValueError("That printer address doesn't look right.")
    port = int(new.get("printer_port", cfg["printer_port"]))
    if not 1 <= port <= 65535:
        raise ValueError("Port must be between 1 and 65535.")
    cfg.update(
        printer_ip=ip,
        printer_port=port,
        cut=bool(new.get("cut", cfg["cut"])),
        vault_path=str(new.get("vault_path", cfg["vault_path"])).strip().strip('"'),
        weekly_note=str(new.get("weekly_note", cfg["weekly_note"])).strip(),
    )
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return cfg


def read_note(rel):
    cfg = load_config()
    if not cfg["vault_path"]:
        raise ValueError("Set your Obsidian vault folder in the Printer settings first.")
    vault = Path(cfg["vault_path"]).expanduser().resolve()
    if not vault.is_dir():
        raise ValueError(f"Vault folder not found: {vault}")
    rel = rel.strip().replace("\\", "/")
    if not rel.lower().endswith(".md"):
        rel += ".md"
    path = (vault / rel).resolve()
    if vault not in path.parents:
        raise ValueError("That note is outside your vault.")
    if not path.is_file():
        raise ValueError(f"Note not found: {rel}")
    return path.name, path.read_text(encoding="utf-8-sig")


def tcp_test(ip, port):
    try:
        with socket.create_connection((ip, port), timeout=4):
            return
    except OSError as e:
        raise ValueError(f"Can't reach {ip}:{port} ({e.strerror or e}). Check the IP address and that the printer is on.")


def build_job(bpr, height, data, cut):
    """ESC/POS: init, raster image in bands (GS v 0), feed, optional partial cut."""
    out = bytearray(b"\x1b@\x1ba\x00")  # ESC @ (reset), ESC a 0 (left align)
    band = 128
    for y in range(0, height, band):
        n = min(band, height - y)
        out += b"\x1dv0\x00" + bpr.to_bytes(2, "little") + n.to_bytes(2, "little")
        out += data[y * bpr:(y + n) * bpr]
    out += b"\x1bd\x04"  # feed 4 lines
    if cut:
        out += b"\x1dVB\x00"  # GS V 66 0: feed to cut position, partial cut
    return bytes(out)


def send_to_printer(ip, port, job):
    with print_lock:
        try:
            with socket.create_connection((ip, port), timeout=6) as s:
                step = 4096
                for i in range(0, len(job), step):
                    s.sendall(job[i:i + step])
                    time.sleep(0.004)
                time.sleep(0.3)
        except OSError as e:
            raise ValueError(f"Couldn't send to {ip}:{port} ({e.strerror or e}).")


class Handler(BaseHTTPRequestHandler):
    server_version = "DailySlip/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (time.strftime("%H:%M:%S"), fmt % args))

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _guard(self):
        # Blocks other websites (and DNS rebinding) from driving the helper.
        if self.headers.get("Host", "") not in HOST_OK:
            self._json(403, {"error": "Open Daily Slip at http://localhost:%d" % PORT})
            return False
        return True

    def do_GET(self):
        if not self._guard():
            return
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            page = HERE / "index.html"
            if not page.is_file():
                return self._json(404, {"error": "index.html is missing next to the helper."})
            body = page.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if not u.path.startswith("/api/") or self.headers.get("X-Daily-Slip") != "1":
            return self._json(404, {"error": "Not found"})
        try:
            if u.path == "/api/config":
                return self._json(200, dict(load_config(), helper=True))
            if u.path == "/api/note":
                name, text = read_note(parse_qs(u.query).get("path", [""])[0])
                return self._json(200, {"name": name, "text": text})
        except ValueError as e:
            return self._json(400, {"error": str(e)})
        self._json(404, {"error": "Not found"})

    def do_POST(self):
        if not self._guard():
            return
        if not self.path.startswith("/api/") or self.headers.get("X-Daily-Slip") != "1":
            return self._json(404, {"error": "Not found"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n > 8_000_000:
                return self._json(413, {"error": "Image too large."})
            body = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/config":
                return self._json(200, dict(save_config(body), helper=True))
            if self.path == "/api/test":
                tcp_test(str(body.get("ip", "")), int(body.get("port", 9100)))
                return self._json(200, {"ok": True})
            if self.path == "/api/print":
                ip, port = str(body.get("ip", "")), int(body.get("port", 9100))
                bpr, height = int(body["width"]), int(body["height"])
                data = base64.b64decode(body["data"])
                if not ip or not (1 <= bpr <= 100) or not (1 <= height <= 20000) or len(data) != bpr * height:
                    raise ValueError("The image data didn't look right. Try printing again.")
                job = build_job(bpr, height, data, bool(body.get("cut", True)))
                send_to_printer(ip, port, job)
                self.log_message("printed %d bytes to %s:%d", len(job), ip, port)
                return self._json(200, {"ok": True, "bytes": len(job)})
        except (ValueError, KeyError, TypeError) as e:
            return self._json(400, {"error": str(e) or "Bad request"})
        self._json(404, {"error": "Not found"})


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"Daily Slip helper running at {url}  (Ctrl+C to stop)")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
