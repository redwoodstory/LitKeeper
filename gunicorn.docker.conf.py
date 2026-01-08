import os

bind = "0.0.0.0:5000"
workers = int(os.getenv("GUNICORN_WORKERS", 1))
worker_class = "sync"
timeout = 300
threads = int(os.getenv("GUNICORN_THREADS", 4))
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

accesslog = "-"
errorlog = "-"
loglevel = "info"

# Simplified access log format: method, path, status code, response time
access_log_format = '%(m)s %(U)s %(s)s %(M)s ms'

preload_app = True
