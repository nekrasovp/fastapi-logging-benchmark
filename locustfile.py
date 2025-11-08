# locustfile.py
from locust import HttpUser, task, constant_pacing, tag


PACE_S = 0.5  # s / user
N_LOGS = 400  # logs / endpoint


class WebsiteUser(HttpUser):
    host = "http://127.0.0.1:8000"
    wait_time = constant_pacing(PACE_S)  # 50 users * (1 request / 0.5 s) = 100 rps

    @tag("baseline")
    @task
    def baseline(self) -> None:
        """Baseline без логирования"""
        self.client.get("/baseline", params={"n": N_LOGS})

    @tag("logs")
    @task
    def default_log(self) -> None:
        """Стандартное синхронное логирование"""
        self.client.get("/logs", params={"n": N_LOGS})

    @tag("aiologger")
    @task
    def aiologger_log(self) -> None:
        """aiologger fire-and-forget (без await)"""
        self.client.get("/aiologger", params={"n": N_LOGS})

    @tag("aiologger-await")
    @task
    def aiologger_await_log(self) -> None:
        """aiologger с явным await"""
        self.client.get("/aiologger-await", params={"n": N_LOGS})

    @tag("custom-async")
    @task
    def custom_async_log(self) -> None:
        """Кастомная async реализация fire-and-forget"""
        self.client.get("/custom-async", params={"n": N_LOGS})

    @tag("custom-async-await")
    @task
    def custom_async_await_log(self) -> None:
        """Кастомная async реализация с await"""
        self.client.get("/custom-async-await", params={"n": N_LOGS})
