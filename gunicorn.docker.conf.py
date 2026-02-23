import os
import sys

REQUIRED_WORKERS = 1

bind = "0.0.0.0:5000"

workers_env = int(os.getenv("GUNICORN_WORKERS", REQUIRED_WORKERS))
if workers_env != REQUIRED_WORKERS:
    print(f"WARNING: GUNICORN_WORKERS={workers_env} not supported with SQLite", file=sys.stderr)
    print(f"Forcing workers={REQUIRED_WORKERS} for data integrity", file=sys.stderr)

workers = REQUIRED_WORKERS
worker_class = "sync"
timeout = 300
threads = int(os.getenv("GUNICORN_THREADS", 4))
keepalive = 5
max_requests = 5000
max_requests_jitter = 100

accesslog = "-"
errorlog = "-"
loglevel = "info"

access_log_format = '%(m)s %(U)s %(s)s %(M)s ms'

preload_app = False


def on_starting(server):
    """Validate configuration on startup"""
    print("=" * 80)
    print("GUNICORN CONFIGURATION")
    print(f"Workers: {workers} (ENFORCED for SQLite + embedded workers)")
    print(f"Threads: {threads}")
    print(f"Preload: {preload_app} (MUST be False)")
    print("=" * 80)

    if workers != REQUIRED_WORKERS:
        print("CRITICAL: Worker enforcement failed!", file=sys.stderr)
        sys.exit(1)
