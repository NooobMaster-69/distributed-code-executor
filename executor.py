import os
import subprocess
import tempfile
import time
from dataclasses import dataclass

from utils import (
    LANGUAGE_MAP,
    validate_code,
    validate_language,
    setup_logger,
)

log = setup_logger("executor")

DEFAULT_TIMEOUT = 10


@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False
    error: str = ""
    language: str = "python"
    duration_ms: float = 0.0

    def to_dict(self):
        return {
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "error": self.error,
            "language": self.language,
            "duration_ms": round(self.duration_ms, 2),
        }


class Executor:

    def __init__(self):
        self.default_timeout = DEFAULT_TIMEOUT

    def safe_env(self):
        keep = {"PATH", "SYSTEMROOT", "TEMP", "TMP", "HOME", "LANG", "COMSPEC"}
        return {k: v for k, v in os.environ.items() if k.upper() in keep}

    def run(self, code, language="python", timeout=DEFAULT_TIMEOUT, user_input=""):
        result = ExecutionResult(language=language)

        lang_err = validate_language(language)
        if lang_err:
            result.error = lang_err
            log.warning("Language rejected: %s", lang_err)
            return result

        sec_err = validate_code(code)
        if sec_err:
            result.error = sec_err
            log.warning("Code blocked: %s", sec_err)
            return result

        lang_cfg = LANGUAGE_MAP[language]
        ext = lang_cfg["ext"]
        cmd_prefix = lang_cfg["cmd"]

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="exec_")
            with os.fdopen(fd, "w", encoding="utf-8") as fp:
                fp.write(code)

            cmd = cmd_prefix + [tmp_path]
            log.info("Running [%s]: %s", language, " ".join(cmd))

            t0 = time.perf_counter()
            proc = subprocess.run(
    cmd,
                input=user_input,   # 🔥 THIS ENABLES input()
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self.safe_env(),
            )
            elapsed = (time.perf_counter() - t0) * 1000

            result.stdout = proc.stdout
            result.stderr = proc.stderr
            result.exit_code = proc.returncode
            result.duration_ms = elapsed

            log.info("Finished [%s] exit=%d duration=%.1fms", language, proc.returncode, elapsed)

        except subprocess.TimeoutExpired:
            result.timed_out = True
            result.error = f"Execution timed out after {timeout}s."
            log.warning("Timeout: code exceeded %ds limit.", timeout)

        except FileNotFoundError:
            result.error = (
                f"Runtime for '{language}' not found. "
                f"Ensure '{cmd_prefix[0]}' is installed and on PATH."
            )
            log.error(result.error)

        except Exception as e:
            result.error = f"Execution error: {e}"
            log.exception("Unexpected execution failure")

        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        return result


executor_instance = Executor()


def execute_code(code, language="python", timeout=DEFAULT_TIMEOUT):
    return executor_instance.run(code, language=language, timeout=timeout)
