import json
import os
import socket
import sys

from utils import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    send_msg,
    recv_msg,
    generate_auth_token,
    setup_logger,
)

log = setup_logger("client")

HOST = os.getenv("EXEC_HOST", DEFAULT_HOST)
PORT = int(os.getenv("EXEC_PORT", str(DEFAULT_PORT)))

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class ExecutionClient:

    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.lang = "python"
        self.tout = 10

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            log.info("Connected to %s:%d", self.host, self.port)
            return True
        except ConnectionRefusedError:
            log.error("Connection refused - is the server running on %s:%d?", self.host, self.port)
            return False
        except Exception as e:
            log.error("Connection failed: %s", e)
            return False

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            log.info("Disconnected.")

    def authenticate(self):
        raw = recv_msg(self.sock)
        if raw is None:
            log.error("No auth challenge received.")
            return False

        msg = json.loads(raw.decode())
        if msg.get("type") != "auth_challenge":
            log.error("Unexpected initial message: %s", msg)
            return False

        challenge = msg["challenge"]
        token = generate_auth_token(challenge)
        send_msg(self.sock, json.dumps({"token": token}).encode())

        raw = recv_msg(self.sock)
        if raw is None:
            log.error("No auth response received.")
            return False

        resp = json.loads(raw.decode())
        if resp.get("status") == "authenticated":
            log.info("Authenticated successfully")
            return True

        log.error("Authentication failed: %s", resp.get("error", "unknown"))
        return False

    def send_code(self, code):
        payload = {
            "code": code,
            "language": self.lang,
            "timeout": self.tout,
        }
        send_msg(self.sock, json.dumps(payload).encode())

        raw = recv_msg(self.sock)
        if raw is None:
            log.error("Server closed connection.")
            return None

        return json.loads(raw.decode())

    def show_banner(self):
        print(f"""
{CYAN}{BOLD}+--------------------------------------------------+
|       Distributed Code Execution Client          |
+--------------------------------------------------+{RESET}
{DIM}Commands:{RESET}
  {GREEN}:file <path>{RESET}   - send a file for execution
  {GREEN}:lang <name>{RESET}   - switch language (python, node, bash, powershell)
  {GREEN}:timeout <s>{RESET}   - set execution timeout in seconds
  {GREEN}:quit{RESET}          - disconnect and exit
  {DIM}(enter a blank line to finish multi-line input){RESET}
""")

    def show_result(self, data):
        st = data.get("status", "unknown")

        if st == "error":
            print(f"\n{RED}Server Error:{RESET} {data.get('error', 'Unknown error')}\n")
            return

        out = data.get("stdout", "")
        err = data.get("stderr", "")
        error = data.get("error", "")
        exitcode = data.get("exit_code", -1)
        timedout = data.get("timed_out", False)
        dur = data.get("duration_ms", 0)
        lang = data.get("language", "?")

        print(f"\n{CYAN}{'-' * 50}")
        print(f" Result  |  lang={lang}  exit={exitcode}  {dur:.1f}ms")
        print(f"{'-' * 50}{RESET}")

        if timedout:
            print(f"{RED}Execution timed out.{RESET}")

        if error:
            print(f"{RED}{error}{RESET}")

        if out:
            print(f"{GREEN}stdout:{RESET}")
            print(out.rstrip())

        if err:
            print(f"{YELLOW}stderr:{RESET}")
            print(err.rstrip())

        print(f"{CYAN}{'-' * 50}{RESET}\n")

    def repl(self):
        self.show_banner()

        while True:
            try:
                code = self.read_input()
                if code is None:
                    break
                if not code.strip():
                    continue

                res = self.send_code(code)
                if res is None:
                    print(f"{RED}Lost connection to server.{RESET}")
                    break
                self.show_result(res)

            except KeyboardInterrupt:
                print(f"\n{DIM}(Ctrl+C - type :quit to exit){RESET}")
            except Exception as e:
                log.error("Client error: %s", e)

    def read_input(self):
        prompt = f"{GREEN}{self.lang}{RESET}> "
        try:
            first = input(prompt)
        except EOFError:
            return None

        if first.startswith(":"):
            return self.handle_cmd(first)

        lines = [first]
        while True:
            try:
                line = input(f"{DIM}...{RESET} ")
            except EOFError:
                break
            if line == "":
                break
            lines.append(line)

        return "\n".join(lines)

    def handle_cmd(self, cmd):
        parts = cmd.split(maxsplit=1)
        directive = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if directive == ":quit":
            return None

        if directive == ":lang":
            if arg:
                self.lang = arg
                print(f"{DIM}Language set to: {arg}{RESET}")
            else:
                print(f"{DIM}Current language: {self.lang}{RESET}")
            return ""

        if directive == ":timeout":
            if arg.isdigit():
                self.tout = int(arg)
                print(f"{DIM}Timeout set to: {self.tout}s{RESET}")
            else:
                print(f"{DIM}Current timeout: {self.tout}s{RESET}")
            return ""

        if directive == ":file":
            if not arg:
                print(f"{RED}Usage: :file <path>{RESET}")
                return ""
            return self.load_file(arg)

        print(f"{YELLOW}Unknown command: {directive}{RESET}")
        return ""

    def load_file(self, path):
        path = os.path.expanduser(path)
        if not os.path.isfile(path):
            print(f"{RED}File not found: {path}{RESET}")
            return ""
        with open(path, "r", encoding="utf-8") as f:
            code = f.read()
        print(f"{DIM}Loaded {len(code)} bytes from {path}{RESET}")
        return code


def main():
    client = ExecutionClient()

    if not client.connect():
        sys.exit(1)

    try:
        if not client.authenticate():
            sys.exit(1)
        client.repl()
    finally:
        client.close()


if __name__ == "__main__":
    main()