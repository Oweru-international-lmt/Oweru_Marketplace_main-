"""Isolated native Celery solo smoke; never imports Django or uses domain data.

Memory transport is intentionally test-only, not application configuration.
Run with the existing Windows virtual environment. No external service is used.
"""
from datetime import timedelta
import json
import threading
from uuid import uuid4

from celery import Celery
from celery.beat import Scheduler
from celery.contrib.testing.worker import start_worker
from celery.result import allow_join_result


def main():
    queue = "windows-smoke-" + uuid4().hex
    app = Celery("native_windows_smoke", broker="memory://",
                 backend="cache+memory://", fixups=[])
    app.conf.update(
        task_always_eager=False, task_default_queue=queue,
        task_serializer="json", result_serializer="json", accept_content=["json"],
        broker_transport_options={"polling_interval": 0.1},
        worker_prefetch_multiplier=1, timezone="Africa/Dar_es_Salaam",
    )
    producer_thread = threading.get_ident()

    @app.task(bind=True, name="native_windows_smoke.retry_once", max_retries=1)
    def retry_once(self):
        if self.request.retries == 0:
            raise self.retry(countdown=0.1)
        return {"retries": self.request.retries,
                "worker_thread": threading.get_ident()}

    @app.task(name="native_windows_smoke.scheduled")
    def scheduled():
        return "beat-dispatched"

    with start_worker(app, pool="solo", concurrency=1, perform_ping_check=False,
                      loglevel="ERROR", shutdown_timeout=10):
        with allow_join_result():
            result = retry_once.delay()
            payload = result.get(timeout=15)
            assert payload["retries"] == 1
            assert payload["worker_thread"] != producer_thread
            assert result.state == "SUCCESS"
            task_id = str(uuid4())
            app.conf.beat_schedule = {
                "isolated-smoke": {
                    "task": scheduled.name, "schedule": timedelta(seconds=1),
                    "options": {"queue": queue, "task_id": task_id},
                }
            }
            scheduler = Scheduler(app=app)
            try:
                scheduler.schedule["isolated-smoke"].last_run_at = (
                    app.now() - timedelta(seconds=2)
                )
                scheduler.tick()
                scheduled_result = app.AsyncResult(task_id)
                assert scheduled_result.get(timeout=15) == "beat-dispatched"
                assert scheduled_result.state == "SUCCESS"
            finally:
                scheduler.close()
    app.close()
    print(json.dumps({"solo_dispatch": "PASS", "retry": "PASS",
                      "beat_dispatch": "PASS", "eager": False,
                      "transport": "memory (test only)",
                      "redis_and_domain_integration": "NOT TESTED"}))


if __name__ == "__main__":
    main()
