# FastAPI logging microbenchmark

A reproducible Locust harness for comparing the request-latency cost of six logging strategies in one async FastAPI application.

[![CI](https://github.com/nekrasovp/fastapi-logging-benchmark/actions/workflows/ci.yml/badge.svg)](https://github.com/nekrasovp/fastapi-logging-benchmark/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

This repository is an experiment, not a universal recommendation to replace Python's standard logging. Logging performance depends on the destination, buffering, container runtime, event loop, host, message format, backpressure, and durability requirements. Run the scenarios in an environment that resembles your own and interpret response latency together with log delivery semantics.

## What it compares

| Scenario | Endpoint behavior | Completion semantics |
|---|---|---|
| `baseline` | Loops without emitting logs | No logging |
| `logs` | Uses a dedicated standard-library `StreamHandler` | Each call writes synchronously |
| `aiologger` | Creates an `aiologger` task for every message | Response does not wait for every write |
| `aiologger-await` | Awaits every `aiologger` task | Response waits for every write |
| `custom-async` | Uses `put_nowait` with an `asyncio.Queue` writer | Response waits only for queue insertion |
| `custom-async-await` | Awaits queue insertion | Response waits for queue insertion, not sink completion |

The fire-and-forget and awaited scenarios do not provide equivalent durability guarantees. A lower response time can mean that work moved beyond the measured request rather than disappeared.

## Quick start

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/nekrasovp/fastapi-logging-benchmark.git
cd fastapi-logging-benchmark
uv sync --locked --group dev
```

Start the benchmark application:

```bash
uv run uvicorn main:app
```

In another terminal, run a short exploratory pass:

```bash
uv run python benchmark.py \
  --run-time 30s \
  --users 20 \
  --spawn-rate 5 \
  --log-volumes 10 100 \
  --pause-seconds 1
```

The original longer profile uses 50 users, a spawn rate of 10, five minutes per scenario, and 100/400 log messages per request:

```bash
uv run python benchmark.py
```

Locust CSV output is written to `results/` and intentionally ignored by Git. Preserve the host specification, dependency lockfile, command, raw CSV files, and environment details when publishing a comparison.

## Method

The Locust user uses constant pacing. With the default 50 users and a 0.5-second pace, the target is approximately 100 requests per second if the application can keep up.

The runner executes one tagged endpoint at a time and passes the log volume through the `N_LOGS` environment variable. It does not rewrite source files between scenarios. For each CSV result it reports:

- minimum response time;
- median response time;
- average response time;
- maximum response time;
- achieved requests per second;
- completed request count;
- request failures.

Compare repeated runs on the same host. Discard runs with failures or resource saturation that differs materially between scenarios.

## Important limitations

- The benchmark writes to process streams; it does not model a network log collector, file rotation, or a vendor agent.
- Response latency is not the same as end-to-end log-delivery latency.
- Fire-and-forget scenarios may have pending work after a response completes.
- Message loss, ordering, shutdown behavior, and backpressure need separate tests.
- Very high log counts per request are stress cases, not a recommended application design.
- A single average is insufficient for a production decision; inspect distributions, failures, CPU, memory, and sink health.

## Verification

```bash
uv run --group dev python -m compileall -q .
uv run --group dev pytest -q
```

CI runs the same compile and test checks on Python 3.12. The test suite verifies application startup, the custom queue endpoint, and Locust aggregate parsing; it deliberately does not run a long load test on shared GitHub-hosted runners. The `aiologger` stream handler requires a real pipe or character device, so its integration path is exercised by the local Uvicorn/Locust run rather than by pytest's captured output stream.

## Repository layout

```text
main.py          FastAPI application and logging strategies
locustfile.py    tagged Locust scenarios
benchmark.py     scenario runner and CSV summarizer
tests/           deterministic smoke and parser tests
```

## License

[MIT](LICENSE)
