import hashlib
import hmac
import logging
import os
import re
import struct

HEADER_SIZE = 4
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9900
MAX_PAYLOAD = 5 * 1024 * 1024
RECV_CHUNK = 4096
AUTH_SECRET = os.getenv("AUTH_SECRET", "s3cur3-sh4red-k3y-2026")

LANGUAGE_MAP = {
    "python": {"cmd": ["python", "-u"], "ext": ".py"},
    "node": {"cmd": ["node"], "ext": ".js"},
    "bash": {"cmd": ["bash"], "ext": ".sh"},
    "powershell": {"cmd": ["powershell", "-NoProfile", "-Command"], "ext": ".ps1"},
}

DANGEROUS_PATTERNS = [
    r"\bshutil\.rmtree\b",
    r"\bos\.remove\b",
    r"\bos\.unlink\b",
    r"\bos\.rmdir\b",
    r"\bos\.system\b",
    r"\b__import__\b",
    r"\bimport\s+subprocess\b",
    r"\bfrom\s+subprocess\b",
    r"\bimport\s+ctypes\b",
    r"\bfrom\s+ctypes\b",
    r"\bimport\s+socket\b",
    r"\bfrom\s+socket\b",
    r"\bimport\s+requests\b",
    r"\bfrom\s+urllib\b",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\bcompile\s*\(",
    r"\brmdir\b",
    r"\bdel\s+/",
    r"\bformat\s+[a-zA-Z]:",
    r"\brm\s+-rf\b",
]

compiled_patterns = [re.compile(p, re.IGNORECASE) for p in DANGEROUS_PATTERNS]


def setup_logger(name, level=logging.DEBUG):
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler()
        fmt = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        h.setFormatter(fmt)
        logger.addHandler(h)
    logger.setLevel(level)
    return logger


def send_msg(sock, data):
    length = len(data)
    header = struct.pack("!I", length)
    sock.sendall(header + data)


def recv_msg(sock):
    raw_hdr = recv_exact(sock, HEADER_SIZE)
    if raw_hdr is None:
        return None
    (msg_len,) = struct.unpack("!I", raw_hdr)
    if msg_len > MAX_PAYLOAD:
        raise ValueError(f"Payload too large: {msg_len} bytes (max {MAX_PAYLOAD})")
    return recv_exact(sock, msg_len)


def recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(RECV_CHUNK, n - len(buf)))
        if not chunk:
            return None
        buf.extend(chunk)
    return bytes(buf)


def generate_auth_token(challenge, secret=AUTH_SECRET):
    return hmac.new(
        secret.encode(), challenge.encode(), hashlib.sha256
    ).hexdigest()


def verify_auth_token(challenge, token, secret=AUTH_SECRET):
    expected = generate_auth_token(challenge, secret)
    return hmac.compare_digest(expected, token)


def validate_code(code):
    for pat in compiled_patterns:
        m = pat.search(code)
        if m:
            return f"Blocked: potentially dangerous pattern '{m.group()}' detected."
    return None


def validate_language(lang):
    if lang not in LANGUAGE_MAP:
        supported = ", ".join(sorted(LANGUAGE_MAP.keys()))
        return f"Unsupported language '{lang}'. Supported: {supported}"
    return None
