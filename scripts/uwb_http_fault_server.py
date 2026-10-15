"""Lab endpoint for firmware delivery tests; never forwards data to production."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.uwb_log_service import BoundedJsonlLog


def make_server(host, port, *, status=200, delay=0, disconnect=False, log_path=None):
    log = BoundedJsonlLog(Path(log_path)) if log_path else None
    # The firmware has one HTTP task. Bound fault-server concurrency too.
    slots = threading.BoundedSemaphore(8)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            if not slots.acquire(blocking=False):
                self.send_error(503)
                return
            try:
                self.connection.settimeout(3)
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 32768:
                    self.send_error(413)
                    return
                payload = json.loads(self.rfile.read(length))
                if log:
                    log.append({"event": "fault_http_received", "received_at_unix": time.time(),
                                "planned_status": status, "delay_seconds": delay,
                                "disconnect": disconnect, "firmware": payload})
                time.sleep(delay)
                if disconnect:
                    self.connection.shutdown(socket.SHUT_RDWR)
                    return
                self.send_response(status)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
            except (OSError, ValueError):
                pass  # Expected when the firmware times out or closes a request.
            finally:
                slots.release()

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--status", type=int, default=200, choices=(200, 422, 429, 500, 503))
    parser.add_argument("--delay", type=float, default=0)
    parser.add_argument("--disconnect", action="store_true")
    parser.add_argument("--log", type=Path, default=Path("logs/uwb-http-fault.jsonl"))
    args = parser.parse_args()
    if not 0 <= args.delay <= 10:
        parser.error("--delay must be between 0 and 10 seconds")
    server = make_server(args.host, args.port, status=args.status, delay=args.delay,
                         disconnect=args.disconnect, log_path=args.log)
    print(f"Lab-only endpoint http://{args.host}:{server.server_port}/api/uwb/distances; "
          f"status={args.status}, delay={args.delay}, disconnect={args.disconnect}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
