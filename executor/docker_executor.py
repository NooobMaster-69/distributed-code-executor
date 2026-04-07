import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone

from models.job import Job, JobStatus

log = logging.getLogger("executor")

DOCKER_LANGS = {
    "python": {"image": "python:3.11-slim", "cmd": ["python", "-u"], "ext": ".py"},
    "node": {"image": "node:20-slim", "cmd": ["node"], "ext": ".js"},
    "bash": {"image": "bash:latest", "cmd": ["bash"], "ext": ".sh"},
}

SUBPROCESS_LANGS = {
    "python": {"cmd": ["python", "-u"], "ext": ".py"},
    "node": {"cmd": ["node"], "ext": ".js"},
    "bash": {"cmd": ["bash"], "ext": ".sh"},
    "powershell": {"cmd": ["powershell", "-NoProfile", "-File"], "ext": ".ps1"},
}

BAD_PATTERNS = [
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
    r"\brm\s+-rf\b",
    r"\brmdir\b",
    r"\bdel\s+/",
    r"\bformat\s+[a-zA-Z]:",
]

compiled_pats = [re.compile(p, re.IGNORECASE) for p in BAD_PATTERNS]


def get_resource_args():
    try:
        from utils.config import (
            DOCKER_CPU_LIMIT,
            DOCKER_MEMORY_LIMIT,
            DOCKER_PIDS_LIMIT,
            DOCKER_STOP_TIMEOUT_SEC,
        )
    except ImportError:
        DOCKER_MEMORY_LIMIT = os.getenv("DOCKER_MEMORY_LIMIT", "50m")
        DOCKER_CPU_LIMIT = os.getenv("DOCKER_CPU_LIMIT", "0.5")
        DOCKER_PIDS_LIMIT = os.getenv("DOCKER_PIDS_LIMIT", "64")
        DOCKER_STOP_TIMEOUT_SEC = int(os.getenv("DOCKER_STOP_TIMEOUT_SEC", "1"))

    return [
        f"--memory={DOCKER_MEMORY_LIMIT}",
        f"--cpus={DOCKER_CPU_LIMIT}",
        f"--pids-limit={DOCKER_PIDS_LIMIT}",
        f"--stop-timeout={DOCKER_STOP_TIMEOUT_SEC}",
    ]


def check_code(code):
    for pat in compiled_pats:
        m = pat.search(code)
        if m:
            return f"Blocked: potentially dangerous pattern '{m.group()}' detected."
    return None


def check_language(lang, docker):
    pool = DOCKER_LANGS if docker else SUBPROCESS_LANGS
    if lang not in pool:
        return f"Unsupported language '{lang}'. Available: {', '.join(sorted(pool))}"
    return None


class CodeExecutor:

    def __init__(self):
        self.docker_available = self.probe_docker()
        mode = "Docker" if self.docker_available else "subprocess (fallback)"
        log.info("CodeExecutor initialized - mode: %s", mode)

    def execute(self, job):
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc).isoformat()

        use_docker = self.docker_available and job.language in DOCKER_LANGS
        lang_err = check_language(job.language, use_docker)
        if lang_err:
            return self.fail(job, lang_err)

        sec_err = check_code(job.code)
        if sec_err:
            return self.fail(job, sec_err)

        if use_docker:
            return self.run_docker(job)
        return self.run_subprocess(job)

    def run_docker(self, job):
        cfg = DOCKER_LANGS[job.language]
        tmp_dir = None

        try:
            tmp_dir = tempfile.mkdtemp(prefix="exec_docker_")
            fname = f"main{cfg['ext']}"
            fpath = os.path.join(tmp_dir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(job.code)

            res_args = get_resource_args()
            cmd = [
                "docker",
                "run",
                "-i",
                "--rm",
                *res_args,
                "--network=none",
                "--read-only",
                "-v",
                f"{tmp_dir}:/code:ro",
                "-w",
                "/code",
                cfg["image"],
                *cfg["cmd"],
                fname,
            ]

            log.info("[%s] Docker run", job.job_id)
            return self.run_process(job, cmd, job.timeout, input_data=job.user_input)

        except Exception as e:
            log.exception("[%s] Docker setup failed", job.job_id)
            return self.fail(job, f"Docker execution error: {e}")
        finally:
            if tmp_dir and os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def run_subprocess(self, job):
        cfg = SUBPROCESS_LANGS[job.language]
        tmp_path = None

        try:
            fd, tmp_path = tempfile.mkstemp(suffix=cfg["ext"], prefix="exec_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(job.code)

            cmd = cfg["cmd"] + [tmp_path]
            log.info("[%s] Subprocess run: %s", job.job_id, " ".join(cmd))
            return self.run_process(job, cmd, job.timeout, env=self.safe_env(), input_data=job.user_input)

        except Exception as e:
            log.exception("[%s] Subprocess setup failed", job.job_id)
            return self.fail(job, f"Subprocess execution error: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def run_process(self, job, cmd, timeout, env=None, input_data=""):
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            elapsed = (time.perf_counter() - t0) * 1000

            job.stdout = proc.stdout or ""
            job.stderr = proc.stderr or ""
            job.exit_code = proc.returncode
            job.execution_time_ms = elapsed
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.status = JobStatus.SUCCESS if proc.returncode == 0 else JobStatus.FAILED

            log.info("[%s] Completed: exit=%d, %.1fms", job.job_id, proc.returncode, elapsed)

        except subprocess.TimeoutExpired as e:
            elapsed = (time.perf_counter() - t0) * 1000
            job.timed_out = True
            job.status = JobStatus.TIMEOUT
            job.error = f"Execution timed out after {timeout}s."
            job.execution_time_ms = elapsed
            if getattr(e, "stdout", None):
                job.stdout = e.stdout if isinstance(e.stdout, str) else e.stdout.decode(errors="replace")
            if getattr(e, "stderr", None):
                job.stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode(errors="replace")
            job.completed_at = datetime.now(timezone.utc).isoformat()
            log.warning("[%s] Timed out after %ds", job.job_id, timeout)

        except FileNotFoundError:
            return self.fail(job, f"Runtime for '{job.language}' not found on PATH.")

        except Exception as e:
            log.exception("[%s] Process run failed", job.job_id)
            return self.fail(job, f"Execution error: {e}")

        return job

    def fail(self, job, error):
        job.status = JobStatus.FAILED
        job.error = error
        job.completed_at = datetime.now(timezone.utc).isoformat()
        log.warning("[%s] %s", job.job_id, error)
        return job

    def safe_env(self):
        keep = {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "LANG", "COMSPEC"}
        return {k: v for k, v in os.environ.items() if k.upper() in keep}

    def probe_docker(self):
        try:
            r = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            return r.returncode == 0
        except Exception:
            return False
