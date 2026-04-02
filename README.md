# Distributed Code Execution Platform

A backend platform for executing untrusted code in isolated environments. Submit code via REST API, have it run inside Docker containers (or sandboxed subprocesses), and poll for results.

Built with FastAPI, with optional Redis-backed job queues for horizontal scaling.

## Table of Contents
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Features](#features)
  - [Core Functionality](#core-functionality)
  - [Supported Languages](#supported-languages)
  - [Security](#security)
- [Architecture](#architecture)
  - [How It Works](#how-it-works)
  - [Technology Stack](#technology-stack)
  - [Project Structure](#project-structure)
- [API Reference](#api-reference)
  - [Submit Code](#post-execute)
  - [Check Status](#get-statusjob_id)
  - [Get Result](#get-resultjob_id)
  - [Health Check](#get-health)
  - [Statistics](#get-stats)
- [Distributed Mode](#distributed-mode)
- [Configuration](#configuration)
- [Contributing](#contributing)
- [Contact](#contact)

## Getting Started

### Prerequisites
- [Python](https://www.python.org/downloads/) 3.11 or higher
- [Docker](https://www.docker.com/get-started/) (optional, recommended for sandboxed execution)
- [Redis](https://redis.io/download/) (optional, only for distributed/multi-process mode)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/NooobMaster-69/distributed-code-executor.git
   cd distributed-code-executor
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate           # Windows
   # source venv/bin/activate      # Linux/macOS
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start the server**
   ```bash
   python -m api.main
   ```

   Swagger docs will be available at `http://localhost:8000/docs`

## Features

### Core Functionality
- **REST API** — Clean FastAPI endpoints with auto-generated OpenAPI/Swagger documentation
- **Docker Sandboxing** — Code runs in isolated, disposable containers with resource limits
- **Subprocess Fallback** — Automatically falls back to sandboxed local execution if Docker isn't available
- **Async Job Queue** — Submit code and poll for results, no blocking
- **Worker Thread Pool** — Configurable number of concurrent execution workers
- **Redis Support** — Optional Redis backend for scaling across multiple processes or machines

### Supported Languages
| Language | Docker | Subprocess |
|----------|--------|------------|
| Python | Yes | Yes |
| Node.js | Yes | Yes |
| Bash | Yes | Yes |
| PowerShell | No | Yes |

### Security

**Docker isolation** (when Docker is available):
- `--network=none` — No outbound network access
- `--read-only` — Immutable filesystem
- `--memory=50m` — Memory cap
- `--cpus=0.5` — CPU throttle
- `--pids-limit=64` — Fork bomb protection
- Container removed after execution (`--rm`)

**Code scanning** — Submitted code is checked against patterns before execution:
- System calls (`os.system`, `subprocess`, `ctypes`)
- File destruction (`shutil.rmtree`, `os.remove`, `rm -rf`)
- Network access (`socket`, `requests`, `urllib`)
- Code injection (`eval`, `exec`, `compile`)

**Subprocess fallback** — When Docker isn't available, code runs with a stripped-down environment. Only `PATH`, `TEMP`, `HOME` and similar safe variables are kept.

**Timeouts** — Enforced per-job with graceful termination.

## Architecture

### How It Works

```
Client (cURL, frontend, etc.)
    |
    |  POST /execute
    v
FastAPI Server
    |
    |  enqueue
    v
Job Queue (in-memory or Redis)
    |
    |  dequeue
    v
Worker Thread Pool
    |
    |  execute
    v
Docker Container          ... or subprocess fallback
  --network=none               (sandboxed env)
  --read-only
  --memory=50m
  --cpus=0.5
```

1. Client submits code + language + timeout via `POST /execute`
2. Server creates a job, queues it, returns a `job_id`
3. A worker picks up the job and runs it in Docker (preferred) or subprocess (fallback)
4. Client polls `GET /result/{job_id}` to retrieve output

**Job lifecycle:** `QUEUED` → `RUNNING` → `SUCCESS` | `FAILED` | `TIMEOUT`

### Technology Stack
- **API Framework** — FastAPI with Pydantic validation
- **Execution** — Docker containers with resource limits, subprocess fallback
- **Queue** — In-memory (threading) or Redis (LPUSH/BRPOP)
- **Workers** — Thread pool with configurable concurrency

### Project Structure
```
api/main.py                  FastAPI app, all endpoints
worker/worker.py             Thread pool, standalone entrypoint
executor/docker_executor.py  Docker + subprocess execution
job_queue/queue_manager.py   In-memory and Redis queue/store
models/job.py                Job dataclass, JobStatus enum
utils/config.py              Env-based settings

server.py, client.py         Legacy TCP socket interface
executor.py, utils.py        Legacy helpers (kept for reference)
```

## API Reference

### `POST /execute`

Submit code for execution.

```bash
curl -X POST http://localhost:8000/execute \
  -H "Content-Type: application/json" \
  -d '{"code": "print(\"hello\")", "language": "python", "timeout": 10}'
```

**Response (202):**
```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "QUEUED",
  "message": "Job queued for execution."
}
```

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `code` | string | required | Max 50KB |
| `language` | string | `"python"` | `python`, `node`, `bash`, `powershell` |
| `timeout` | int | `10` | 1–30 seconds |

### `GET /status/{job_id}`

Returns current status: `QUEUED`, `RUNNING`, `SUCCESS`, `FAILED`, or `TIMEOUT`.

### `GET /result/{job_id}`

Returns the full execution result.

```json
{
  "job_id": "a1b2c3d4e5f6",
  "status": "SUCCESS",
  "output": "hello\n",
  "stdout": "hello\n",
  "stderr": "",
  "error": "",
  "exit_code": 0,
  "timed_out": false,
  "language": "python",
  "execution_time": 0.0123,
  "execution_time_ms": 12.3,
  "created_at": "2026-04-02T18:30:00+00:00",
  "started_at": "2026-04-02T18:30:00.050+00:00",
  "completed_at": "2026-04-02T18:30:00.062+00:00"
}
```

### `GET /health`

Server health, executor mode (docker/subprocess), queue backend (memory/redis).

### `GET /stats`

Queue depth and job counts by status.

## Distributed Mode

Scale workers across processes or machines using Redis as the shared backend.

**API server (Terminal 1):**
```bash
set REDIS_URL=redis://localhost:6379/0
set RUN_EMBEDDED_WORKER=false
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Worker processes (Terminal 2+):**
```bash
set REDIS_URL=redis://localhost:6379/0
python -m worker.worker
```

Run as many worker processes as you need. All workers pointing to the same `REDIS_URL` share the queue.

## Configuration

All settings are controlled through environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Port |
| `WORKER_THREADS` | `4` | Concurrent execution threads |
| `RUN_EMBEDDED_WORKER` | `true` | Run workers inside API process |
| `REDIS_URL` | *(empty)* | Set to enable distributed mode |
| `REDIS_KEY_PREFIX` | `exec:` | Namespace for Redis keys |
| `DOCKER_MEMORY_LIMIT` | `50m` | Container memory limit |
| `DOCKER_CPU_LIMIT` | `0.5` | Container CPU limit |
| `DOCKER_PIDS_LIMIT` | `64` | Container PID limit |
| `DOCKER_STOP_TIMEOUT_SEC` | `1` | Seconds before force-killing container |

## Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -m 'Add your feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Open a Pull Request

## Contact
- **Issues**: [GitHub Issues](https://github.com/NooobMaster-69/distributed-code-executor/issues)
- **GitHub**: [NooobMaster-69](https://github.com/NooobMaster-69)
