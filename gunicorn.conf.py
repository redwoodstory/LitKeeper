bind = "0.0.0.0:5017"
workers = 1
worker_class = "sync"
timeout = 120
threads = 4
keepalive = 5
max_requests = 1000
max_requests_jitter = 50

accesslog = "-"
errorlog = "-"
loglevel = "info"

preload_app = True
