"""Small dependency-free concurrent health endpoint benchmark."""
import argparse
import concurrent.futures
import statistics
import time
import urllib.request


def hit(url: str) -> float:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=5) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
    return (time.perf_counter() - started) * 1000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000/health")
    parser.add_argument("--requests", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()
    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        latencies = list(pool.map(lambda _: hit(args.url), range(args.requests)))
    elapsed = time.perf_counter() - started
    ordered = sorted(latencies)
    print({"requests": args.requests, "seconds": round(elapsed, 3), "requests_per_second": round(args.requests / elapsed, 1), "p50_ms": round(statistics.median(ordered), 2), "p95_ms": round(ordered[int(len(ordered) * 0.95) - 1], 2)})


if __name__ == "__main__":
    main()
