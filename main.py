# main.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn
from aiologger import Logger
from aiologger.levels import LogLevel


LOG_FORMAT = (
    "[%(asctime)s.%(msecs)03d] "
    "[%(threadName)s] "
    "%(funcName)20s "
    "%(module)s:%(lineno)d "
    "%(levelname)-8s - "
    "%(message)s"
)
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
log = logging.getLogger("benchmark.standard")


def configure_default_logger(level: str = "INFO") -> None:
    """Configure the synchronous logger independently from Uvicorn."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATEFMT))
    log.handlers.clear()
    log.addHandler(handler)
    log.setLevel(level)
    log.propagate = False

# Глобальные переменные для async логирования
aiolog = None
custom_log_queue = None
custom_log_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global aiolog, custom_log_queue, custom_log_task
    configure_default_logger()
    aiolog = Logger.with_default_handlers(
        name='fastapi-logger',
        level=LogLevel.INFO
    )
    custom_log_queue = asyncio.Queue()
    custom_log_task = asyncio.create_task(custom_log_writer())
    yield
    # Shutdown
    if aiolog:
        await aiolog.shutdown()
    if custom_log_queue:
        await custom_log_queue.join()
    if custom_log_task:
        custom_log_task.cancel()
        try:
            await custom_log_task
        except asyncio.CancelledError:
            pass

app = FastAPI(lifespan=lifespan)


async def custom_log_writer():
    """
    Background coroutine для записи логов из asyncio.Queue.
    Кастомная реализация без внешних библиотек.
    """
    while True:
        try:
            record = await custom_log_queue.get()
            # Запись в stdout (можно заменить на file или другой handler)
            print(f"[CUSTOM] {record}")
            custom_log_queue.task_done()
        except asyncio.CancelledError:
            # Обработка завершения при shutdown
            break


@app.get("/baseline")
async def baseline(n: int) -> dict[str, bool]:
    """Baseline без логирования"""
    for _ in range(n):
        pass
    return {"ok": True}


@app.get("/logs")
async def logs(n: int) -> dict[str, bool]:
    """Стандартное синхронное логирование"""
    for _ in range(n):
        log.info("done.")
    return {"ok": True}


@app.get("/aiologger")
async def aiologger_endpoint(n: int) -> dict[str, bool]:
    """
    aiologger БЕЗ await - fire-and-forget режим.
    Логи помещаются в очередь и возвращается управление немедленно.
    Самый быстрый вариант для высокопроизводительных приложений.
    """
    for _ in range(n):
        # Fire-and-forget: логи уходят в очередь асинхронно
        aiolog.info("done.")
    
    return {"ok": True}


@app.get("/aiologger-await")
async def aiologger_await_endpoint(n: int) -> dict[str, bool]:
    """
    aiologger С await - явно ждем записи каждого лога.
    Медленнее fire-and-forget, но гарантирует порядок и запись.
    Используйте для критичных логов.
    """
    for _ in range(n):
        # Ждем записи каждого лога
        await aiolog.info("done.")
    
    return {"ok": True}


@app.get("/custom-async")
async def custom_async_endpoint(n: int) -> dict[str, bool]:
    """
    Кастомная реализация async логирования с asyncio.Queue.
    Альтернатива aiologger без внешних зависимостей.
    Fire-and-forget режим - логи помещаются в очередь немедленно.
    """
    for _ in range(n):
        # Помещаем сообщение в очередь без ожидания записи
        custom_log_queue.put_nowait("done.")
    
    return {"ok": True}


@app.get("/custom-async-await")
async def custom_async_await_endpoint(n: int) -> dict[str, bool]:
    """
    Кастомная async реализация С await.
    Явно ждем помещения каждого сообщения в очередь.
    """
    for _ in range(n):
        # Явно ждем помещения в очередь (хотя put обычно мгновенный)
        await custom_log_queue.put("done.")
    
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app)
