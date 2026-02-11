"""Prometheus metrics for the bot."""
from prometheus_client import Counter, Gauge, Histogram, Info
from prometheus_client import make_wsgi_app, REGISTRY
from wsgiref.simple_server import make_server, WSGIRequestHandler, WSGIServer
from socketserver import ThreadingMixIn
import threading
import logging

# Bot info
BOT_INFO = Info("bot", "Bot information")

# Command counters
COMMANDS_TOTAL = Counter(
    "bot_commands_total",
    "Total number of commands processed",
    ["command"]
)

# Callback counters
CALLBACKS_TOTAL = Counter(
    "bot_callbacks_total",
    "Total number of callback queries processed",
    ["action"]
)

# Response counters (player votes)
RESPONSES_TOTAL = Counter(
    "bot_responses_total",
    "Total number of player responses",
    ["status"]
)

# Error counter
ERRORS_TOTAL = Counter(
    "bot_errors_total",
    "Total number of errors",
    ["type"]
)

# Active sessions gauge
ACTIVE_SESSIONS = Gauge(
    "bot_active_sessions",
    "Number of active (open) sessions"
)

# Players in current session
PLAYERS_CURRENT = Gauge(
    "bot_players_current",
    "Number of players in current session",
    ["status"]
)

# Request duration histogram - уменьшено количество buckets для экономии памяти
REQUEST_DURATION = Histogram(
    "bot_request_duration_seconds",
    "Request processing duration in seconds",
    ["handler"],
    buckets=[0.05, 0.1, 0.5, 1.0, 5.0]  # Было 9 buckets, стало 5
)

# Scheduler job executions
SCHEDULER_JOBS_TOTAL = Counter(
    "bot_scheduler_jobs_total",
    "Total number of scheduler job executions",
    ["job"]
)

# Guests added counter
GUESTS_ADDED_TOTAL = Counter(
    "bot_guests_added_total",
    "Total number of guest participants added"
)

# Guests deleted counter
GUESTS_DELETED_TOTAL = Counter(
    "bot_guests_deleted_total",
    "Total number of guest participants deleted"
)

# Team changes counter
TEAM_CHANGES_TOTAL = Counter(
    "bot_team_changes_total",
    "Total number of team changes",
    ["team"]
)

# Team selections counter (when users first select their team)
TEAM_SELECTIONS_TOTAL = Counter(
    "bot_team_selections_total",
    "Total number of team selections by users",
    ["team"]
)


class _QuietHandler(WSGIRequestHandler):
    """WSGI handler без логирования запросов и с таймаутом на сокетах."""

    # Таймаут чтения запроса — не даём зависшим подключениям блокировать сервер
    timeout = 5

    def log_message(self, format, *args):
        pass  # Не логируем каждый scrape от Prometheus

    def handle(self):
        """Обработка запроса с таймаутом на сокете."""
        self.request.settimeout(self.timeout)
        try:
            super().handle()
        except (TimeoutError, OSError):
            pass  # Сканер/медленный клиент — молча закрываем


class _ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    """Многопоточный WSGI-сервер: каждый запрос в отдельном потоке.

    Одно зависшее подключение не блокирует остальные (healthcheck, Prometheus).
    """
    daemon_threads = True


def start_metrics_server(port: int = 8000) -> None:
    """Start the Prometheus metrics HTTP server with minimal overhead."""
    logging.info(f"Starting metrics server on 0.0.0.0:{port}")
    try:
        app = make_wsgi_app(registry=REGISTRY)
        httpd = make_server(
            '0.0.0.0', port, app,
            handler_class=_QuietHandler,
            server_class=_ThreadingWSGIServer,
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        logging.info(f"Metrics server started successfully on 0.0.0.0:{port}")
    except OSError as e:
        if "Address already in use" in str(e):
            logging.error(f"Port {port} is already in use. Metrics server not started.")
        else:
            logging.error(f"Failed to start metrics server: {e}", exc_info=True)
            raise
    except Exception as e:
        logging.error(f"Failed to start metrics server: {e}", exc_info=True)
        raise


def set_bot_info(name: str, username: str, bot_id: int) -> None:
    """Set bot information metric."""
    BOT_INFO.info({
        "name": name,
        "username": username,
        "id": str(bot_id)
    })
