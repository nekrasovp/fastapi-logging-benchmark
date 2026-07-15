import os

from locust import HttpUser, task, constant_pacing, tag


PACE_S = 0.5  # s / user
N_LOGS = int(os.environ.get("N_LOGS", "400"))


class WebsiteUser(HttpUser):
    host = "http://127.0.0.1:8000"
    wait_time = constant_pacing(PACE_S)  # 50 users * (1 request / 0.5 s) = 100 rps

    @tag("baseline")
    @task
    def baseline(self) -> None:
        """Exercise the no-logging baseline."""
        self.client.get("/baseline", params={"n": N_LOGS})

    @tag("logs")
    @task
    def default_log(self) -> None:
        """Exercise synchronous standard-library logging."""
        self.client.get("/logs", params={"n": N_LOGS})

    @tag("aiologger")
    @task
    def aiologger_log(self) -> None:
        """Exercise aiologger without awaiting every call."""
        self.client.get("/aiologger", params={"n": N_LOGS})

    @tag("aiologger-await")
    @task
    def aiologger_await_log(self) -> None:
        """Exercise aiologger while awaiting every call."""
        self.client.get("/aiologger-await", params={"n": N_LOGS})

    @tag("custom-async")
    @task
    def custom_async_log(self) -> None:
        """Exercise non-blocking insertion into the custom queue."""
        self.client.get("/custom-async", params={"n": N_LOGS})

    @tag("custom-async-await")
    @task
    def custom_async_await_log(self) -> None:
        """Exercise awaited insertion into the custom queue."""
        self.client.get("/custom-async-await", params={"n": N_LOGS})
