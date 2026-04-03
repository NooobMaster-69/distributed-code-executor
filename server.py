import json
import os
import socket
import threading
import uuid

from utils import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    send_msg,
    recv_msg,
    generate_auth_token,
    verify_auth_token,
    setup_logger,
)
from executor import execute_code

log = setup_logger("server")

HOST = os.getenv("EXEC_HOST", DEFAULT_HOST)
PORT = int(os.getenv("EXEC_PORT", str(DEFAULT_PORT)))
MAX_CLIENTS = int(os.getenv("EXEC_MAX_CLIENTS", "20"))
EXEC_TIMEOUT = int(os.getenv("EXEC_TIMEOUT", "10"))


class ClientHandler(threading.Thread):

    def __init__(self, conn, addr):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.cid = str(uuid.uuid4())[:8]
        self.authed = False

    def run(self):
        tag = f"[{self.cid}@{self.addr[0]}:{self.addr[1]}]"
        log.info("%s Connected", tag)
        try:
            if not self.do_auth(tag):
                self.send_err("Authentication failed.")
                return

            self.authed = True
            log.info("%s Authenticated", tag)
            self.send_json({"status": "authenticated", "message": "Ready for code execution."})

            while True:
                raw = recv_msg(self.conn)
                if raw is None:
                    log.info("%s Disconnected", tag)
                    break

                self.process(raw, tag)

        except ConnectionResetError:
            log.warning("%s Connection reset", tag)
        except Exception as e:
            log.exception("%s Unexpected error: %s", tag, e)
        finally:
            self.conn.close()
            log.info("%s Socket closed", tag)

    def do_auth(self, tag):
        challenge = uuid.uuid4().hex
        self.send_json({"type": "auth_challenge", "challenge": challenge})

        raw = recv_msg(self.conn)
        if raw is None:
            return False

        try:
            msg = json.loads(raw.decode())
            tok = msg.get("token", "")
        except (json.JSONDecodeError, UnicodeDecodeError):
            log.warning("%s Malformed auth response", tag)
            return False

        if not verify_auth_token(challenge, tok):
            log.warning("%s Invalid auth token", tag)
            return False

        return True

    def process(self, raw, tag):
        try:
            req = json.loads(raw.decode())
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_err("Invalid JSON payload.")
            return

        code = req.get("code")
        if not code or not isinstance(code, str):
            self.send_err("Missing or invalid 'code' field.")
            return

        lang = req.get("language", "python").lower().strip()
        tout = min(int(req.get("timeout", EXEC_TIMEOUT)), 30)

        log.info("%s Executing %d bytes of %s (timeout=%ds)", tag, len(code), lang, tout)

        res = execute_code(code, language=lang, timeout=tout)
        self.send_json({"status": "result", **res.to_dict()})

    def send_json(self, obj):
        send_msg(self.conn, json.dumps(obj).encode())

    def send_err(self, msg):
        self.send_json({"status": "error", "error": msg})


def start_server(host=HOST, port=PORT):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((host, port))
    srv.listen(MAX_CLIENTS)

    log.info("=" * 55)
    log.info("  Code Execution Server listening on %s:%d", host, port)
    log.info("  Max clients: %d | Timeout: %ds", MAX_CLIENTS, EXEC_TIMEOUT)
    log.info("=" * 55)

    try:
        while True:
            conn, addr = srv.accept()
            handler = ClientHandler(conn, addr)
            handler.start()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        srv.close()
        log.info("Server socket closed.")


if __name__ == "__main__":
    start_server()