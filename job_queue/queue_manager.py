import json
import logging
import os
import threading
from collections import deque

from models.job import Job, JobStatus

log = logging.getLogger("queue_manager")


class JobQueue:

    def __init__(self):
        self.queue = deque()
        self.cond = threading.Condition()

    def put(self, job):
        with self.cond:
            self.queue.append(job)
            self.cond.notify()
            log.info("Enqueued job %s (%s) - queue size: %d", job.job_id, job.language, len(self.queue))

    def get(self, timeout=1.0):
        with self.cond:
            while not self.queue:
                if not self.cond.wait(timeout=timeout):
                    return None
            return self.queue.popleft()

    @property
    def size(self):
        with self.cond:
            return len(self.queue)


class JobStore:

    def __init__(self):
        self.lock = threading.RLock()
        self.jobs = {}

    def save(self, job):
        with self.lock:
            self.jobs[job.job_id] = job

    def get(self, job_id):
        with self.lock:
            return self.jobs.get(job_id)

    def list_by_status(self, status):
        with self.lock:
            return [j for j in self.jobs.values() if j.status == status]

    def count(self):
        with self.lock:
            counts = {}
            for job in self.jobs.values():
                key = job.status.value
                counts[key] = counts.get(key, 0) + 1
            return counts


class RedisJobQueue:
    def __init__(self, client, key_prefix, store):
        self.r = client
        self.qkey = f"{key_prefix}queue"
        self.store = store

    def put(self, job):
        self.r.lpush(self.qkey, job.job_id)
        log.info("Redis enqueued job %s - queue len: %d", job.job_id, self.size)

    def get(self, timeout=1.0):
        t = int(max(1, min(60, timeout)))
        item = self.r.brpop(self.qkey, timeout=t)
        if not item:
            return None
        job_id = item[1]
        job = self.store.get(job_id)
        if job is None:
            log.error("Missing job payload for queued id %s", job_id)
        return job

    @property
    def size(self):
        return int(self.r.llen(self.qkey))


class RedisJobStore:
    def __init__(self, client, key_prefix):
        self.r = client
        self.prefix = key_prefix

    def job_key(self, job_id):
        return f"{self.prefix}job:{job_id}"

    def jobs_set_key(self):
        return f"{self.prefix}job_ids"

    def save(self, job):
        payload = json.dumps(job.to_dict(), ensure_ascii=False)
        self.r.set(self.job_key(job.job_id), payload)
        self.r.sadd(self.jobs_set_key(), job.job_id)

    def get(self, job_id):
        raw = self.r.get(self.job_key(job_id))
        if not raw:
            return None
        try:
            return Job.from_dict(json.loads(raw))
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            log.error("Corrupt job %s: %s", job_id, e)
            return None

    def list_by_status(self, status):
        out = []
        for jid in self.r.smembers(self.jobs_set_key()):
            j = self.get(jid)
            if j and j.status == status:
                out.append(j)
        return out

    def count(self):
        counts = {}
        for jid in self.r.smembers(self.jobs_set_key()):
            j = self.get(jid)
            if j:
                key = j.status.value
                counts[key] = counts.get(key, 0) + 1
        return counts


def build_queue_backend():
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return JobQueue(), JobStore()

    import redis

    client = redis.Redis.from_url(url, decode_responses=True)
    prefix = os.getenv("REDIS_KEY_PREFIX", "exec:")
    store = RedisJobStore(client, prefix)
    queue = RedisJobQueue(client, prefix, store)
    log.info("Queue backend: Redis (%s, prefix=%s)", url.split("@")[-1], prefix)
    return queue, store
