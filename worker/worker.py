import logging
import os
import signal
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from executor.docker_executor import CodeExecutor
from models.job import Job, JobStatus
from job_queue.queue_manager import (
    JobQueue,
    JobStore,
    RedisJobQueue,
    RedisJobStore,
    build_queue_backend,
)

log = logging.getLogger("worker")


class Worker:

    def __init__(self, job_queue, job_store, num_threads=4):
        self.job_queue = job_queue
        self.job_store = job_store
        self.num_threads = num_threads
        self.executor = CodeExecutor()
        self.threads = []
        self.running = False

    def start(self):
        if self.running:
            log.warning("Worker already running")
            return

        self.running = True

        for i in range(self.num_threads):
            name = f"worker-{i}"
            t = threading.Thread(target=self.loop, name=name, daemon=True)
            t.start()
            self.threads.append(t)

        log.info(
            "Worker started: %d threads, executor=%s",
            self.num_threads,
            "docker" if self.executor.docker_available else "subprocess",
        )

    def stop(self, timeout=5.0):
        self.running = False
        for t in self.threads:
            t.join(timeout=timeout)
        self.threads.clear()
        log.info("Worker stopped")

    @property
    def is_running(self):
        return self.running

    def loop(self):
        tname = threading.current_thread().name

        while self.running:
            job = self.job_queue.get(timeout=1.0)
            if job is None:
                continue

            log.info("[%s] Processing job %s (%s, %d bytes)", tname, job.job_id, job.language, len(job.code))

            try:
                self.executor.execute(job)
            except Exception as e:
                job.status = JobStatus.FAILED
                job.error = f"Worker error: {e}"
                log.exception("[%s] Unhandled error on job %s", tname, job.job_id)

            try:
                self.job_store.save(job)
            except Exception as e:
                log.exception("[%s] Failed to persist job %s: %s", tname, job.job_id, e)

            log.info("[%s] Job %s -> %s (%.1fms)", tname, job.job_id, job.status.value, job.execution_time_ms)


def run_worker():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    from utils.config import WORKER_THREADS

    jq, js = build_queue_backend()
    if not os.getenv("REDIS_URL", "").strip():
        log.warning("REDIS_URL not set")

    w = Worker(jq, js, num_threads=WORKER_THREADS)
    w.start()

    stop_evt = threading.Event()

    def on_signal(*args):
        log.info("Shutdown signal received")
        stop_evt.set()

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    try:
        while not stop_evt.wait(0.5):
            pass
    finally:
        w.stop()


if __name__ == "__main__":
    run_worker()