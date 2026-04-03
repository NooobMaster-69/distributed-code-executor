import os


def env_bool(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def env_int(name, default):
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    try:
        return int(v)
    except ValueError:
        return default


def env_float(name, default):
    v = os.getenv(name)
    if v is None or not v.strip():
        return default
    try:
        return float(v)
    except ValueError:
        return default


API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = env_int("API_PORT", 8000)

WORKER_THREADS = env_int("WORKER_THREADS", 4)
RUN_EMBEDDED_WORKER = env_bool("RUN_EMBEDDED_WORKER", True)

DOCKER_MEMORY_LIMIT = os.getenv("DOCKER_MEMORY_LIMIT", "50m")
DOCKER_CPU_LIMIT = os.getenv("DOCKER_CPU_LIMIT", "0.5")
DOCKER_PIDS_LIMIT = os.getenv("DOCKER_PIDS_LIMIT", "64")
DOCKER_STOP_TIMEOUT_SEC = env_int("DOCKER_STOP_TIMEOUT_SEC", 1)
