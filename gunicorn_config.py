import multiprocessing

# Diretório do projeto
bind = "127.0.0.1:8000"

# Workers (2-4 x CPU cores)
#workers = multiprocessing.cpu_count() * 2 + 1
workers = 12

worker_class = "sync"

# Timeouts
timeout = 120
keepalive = 5

# Logs
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

# Processo
daemon = False
pidfile = "/run/gunicorn/gunicorn.pid"

# Segurança
limit_request_line = 4096
limit_request_fields = 100
limit_request_field_size = 8190
