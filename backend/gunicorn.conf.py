import os

bind = "0.0.0.0:8000"
workers = int(os.getenv("WEB_WORKERS", "2"))
threads = int(os.getenv("WEB_THREADS", "2"))
worker_class = "gthread"
timeout = 60
graceful_timeout = 30
max_requests = 1000
max_requests_jitter = 100
accesslog = None  # Application middleware logs route templates without query tokens.
errorlog = "-"
capture_output = True
forwarded_allow_ips = os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1")
