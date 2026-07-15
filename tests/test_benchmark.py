from pathlib import Path

from benchmark import LocustBenchmark


def test_parse_aggregated_locust_stats(tmp_path: Path) -> None:
    stats_file = tmp_path / "stats.csv"
    stats_file.write_text(
        "Type,Name,Request Count,Failure Count,Median Response Time,"
        "Average Response Time,Min Response Time,Max Response Time,Requests/s\n"
        ",Aggregated,10,0,12,14.5,3,40,9.8\n",
        encoding="utf-8",
    )

    stats = LocustBenchmark().parse_stats_csv(str(stats_file))

    assert stats == {
        "min": 3.0,
        "median": 12.0,
        "avg": 14.5,
        "max": 40.0,
        "rps": 9.8,
        "requests": 10,
        "failures": 0,
    }
