# main.py
import asyncio
import logging
from contextlib import asynccontextmanager

from aiologger import Logger
from aiologger.levels import LogLevel
from fastapi import FastAPI
import uvicorn


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

aiolog = None
custom_log_queue = None
custom_log_task = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global aiolog, custom_log_queue, custom_log_task
    configure_default_logger()
    aiolog = Logger.with_default_handlers(
        name="fastapi-logger",
        level=LogLevel.INFO,
    )
    custom_log_queue = asyncio.Queue()
    custom_log_task = asyncio.create_task(custom_log_writer())
    yield

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
    """Write messages from the custom asyncio queue to stdout."""
    while True:
        try:
            record = await custom_log_queue.get()
            print(f"[CUSTOM] {record}")
            custom_log_queue.task_done()
        except asyncio.CancelledError:
            break


@app.get("/baseline")
async def baseline(n: int) -> dict[str, bool]:
    """Run the comparison loop without emitting logs."""
    for _ in range(n):
        pass
    return {"ok": True}


@app.get("/logs")
async def logs(n: int) -> dict[str, bool]:
    """Emit messages synchronously through the standard logging package."""
    for _ in range(n):
        log.info("done.")
    return {"ok": True}


@app.get("/aiologger")
async def aiologger_endpoint(n: int) -> dict[str, bool]:
    """Schedule aiologger calls without awaiting each returned task."""
    for _ in range(n):
        aiolog.info("done.")

    return {"ok": True}


@app.get("/aiologger-await")
async def aiologger_await_endpoint(n: int) -> dict[str, bool]:
    """Await every aiologger call before scheduling the next message."""
    for _ in range(n):
        await aiolog.info("done.")

    return {"ok": True}


@app.get("/custom-async")
async def custom_async_endpoint(n: int) -> dict[str, bool]:
    """Insert messages into the custom queue without waiting for its sink."""
    for _ in range(n):
        custom_log_queue.put_nowait("done.")

    return {"ok": True}


@app.get("/custom-async-await")
async def custom_async_await_endpoint(n: int) -> dict[str, bool]:
    """Await insertion into the custom queue, not completion at its sink."""
    for _ in range(n):
        await custom_log_queue.put("done.")

    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run(app)
