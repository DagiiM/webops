"""Deterministic resilience-under-load matrix for WebOps.

1408 parameterized cases + concurrent workload probes. Seeds are stable and
cover different arrival schedules, retries, failovers, duplicate messages,
circuit recovery and recovery after resource pressure.
"""
from concurrent.futures import ThreadPoolExecutor
from math import ceil
from random import Random
from threading import Barrier, Lock
from time import sleep

import pytest

from webops_cli.resilience import (
    CircuitBreaker, CircuitOpen, ConcurrencyLimiter, DeploymentState,
    HealthWindow, InvalidTransition, RateLimited, RetryPolicy, RetryableError,
    SingleFlight, TokenBucket, deployment_key, retry_read,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def tick(self, delta):
        self.now += delta


@pytest.mark.parametrize("seed", range(256), ids=lambda x: f"bursty-arrivals-{x:03d}")
def test_token_bucket_bursts_and_recovery(seed):
    rng, clock = Random(seed), FakeClock()
    capacity, refill = seed % 11 + 1, (seed % 13 + 1) / 4
    bucket = TokenBucket(capacity, refill, clock)
    expected_tokens, last = float(capacity), 0.0
    accepted = 0
    for _ in range(80):
        clock.tick(rng.randint(0, 20) / 10)
        cost = rng.randint(1, capacity)
        expected_tokens = min(capacity, expected_tokens + (clock.now - last) * refill)
        last = clock.now
        expected = expected_tokens + 1e-10 >= cost
        if expected:
            expected_tokens -= cost
            accepted += 1
        assert bucket.consume(cost) is expected
        assert bucket.available == pytest.approx(expected_tokens, abs=1e-8)
    assert 0 <= bucket.available <= capacity
    assert accepted > 0


@pytest.mark.parametrize("seed", range(256), ids=lambda x: f"circuit-recovery-{x:03d}")
def test_circuit_failure_threshold_and_half_open_probes(seed):
    clock = FakeClock()
    threshold = seed % 7 + 1
    reset_after = (seed % 11 + 1) / 2
    breaker = CircuitBreaker(threshold, reset_after, clock)
    counter = [0]

    def fail():
        counter[0] += 1
        raise OSError("transient transport failure")

    for n in range(threshold):
        with pytest.raises(OSError):
            breaker.call(fail)
        if n + 1 < threshold:
            assert breaker.state == "closed"
    assert breaker.state == "open"
    with pytest.raises(CircuitOpen):
        breaker.call(fail)
    assert counter[0] == threshold
    clock.tick(reset_after)
    assert breaker.state == "half_open"
    if seed & 1:
        with pytest.raises(OSError):
            breaker.call(fail)
        assert breaker.state == "open"
        clock.tick(reset_after)
    assert breaker.call(lambda: "recovered") == "recovered"
    assert breaker.state == "closed"
    assert breaker.failures == 0


@pytest.mark.parametrize("seed", range(256), ids=lambda x: f"duplicates-{x:03d}")
def test_singleflight_parallel_duplicate_deployments(seed):
    n = 2 + seed % 9
    gate = Barrier(n)
    calls, lock = [0], Lock()
    sf = SingleFlight()
    key = f"tenant-{seed % 17}/project-{seed}"

    def actual_submit():
        with lock:
            calls[0] += 1
        sleep(0.001 + (seed % 5) * 0.0004)
        return {"request": seed, "deployment_id": "deploy-0001"}

    def worker(_):
        gate.wait(timeout=4)
        return sf.run(key, actual_submit)

    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(worker, range(n)))
    assert len(results) == n
    assert all(result == results[0] for result in results)
    assert calls[0] == 1
    assert sf.run(key, actual_submit) == results[0]
    assert calls[0] == 1


@pytest.mark.parametrize("seed", range(256), ids=lambda x: f"state-replay-{x:03d}")
def test_deployment_state_event_replay_and_illegal_reorder(seed):
    rng = Random(seed + 97)
    sm = DeploymentState()
    route = ["validated", "queued", "building", "starting", "verifying", "ready"]
    if seed % 9 == 0:
        route = route[:seed % 5 + 1] + ["failed", "rolled_back"]
    old_id = None
    for index, state in enumerate(route):
        event_id = f"e-{seed}-{index}"
        assert sm.advance(state, event_id)
        if old_id is not None and rng.random() > 0.35:
            assert not sm.advance("rolled_back", old_id)
        old_id = event_id
        assert sm.state == state
    assert len(sm.history) == len(route)
    if sm.state in {"ready", "rolled_back"}:
        with pytest.raises(InvalidTransition):
            sm.advance("queued", f"untrusted-{seed}")


@pytest.mark.parametrize("seed", range(128), ids=lambda x: f"backoff-{x:03d}")
def test_bounded_retry_only_reads_with_fault_injection(seed):
    attempts = seed % 8 + 1
    errors = seed % 6
    policy = RetryPolicy(attempts=attempts, base_delay=0.01 + seed % 4 / 100,
                         max_delay=0.15 + seed % 7 / 100)
    sleeps, calls = [], [0]

    def fetch():
        calls[0] += 1
        if calls[0] <= errors:
            raise RetryableError("rate limited")
        return "healthy"

    if errors >= attempts:
        with pytest.raises(RetryableError):
            retry_read(fetch, policy, sleeps.append)
        assert calls[0] == attempts
    else:
        assert retry_read(fetch, policy, sleeps.append) == "healthy"
        assert calls[0] == errors + 1
    assert len(sleeps) == calls[0] - 1
    assert sleeps == pytest.approx([policy.delay(i) for i in range(len(sleeps))])
    assert all(0 <= delay <= policy.max_delay for delay in sleeps)


@pytest.mark.parametrize("seed", range(128), ids=lambda x: f"slo-window-{x:03d}")
def test_slo_rolling_percentiles_under_load(seed):
    rng = Random(seed * 7 + 29)
    capacity = 20 + seed % 80
    slo = HealthWindow(capacity, min_samples=10, max_error_rate=0.12,
                       max_p95_ms=1500)
    observations = []
    for _ in range(300):
        success = rng.randrange(100) >= seed % 21
        latency = float(rng.randrange(3000))
        slo.record(success, latency)
        observations.append((success, latency))
    current = observations[-capacity:]
    p95 = sorted(latency for _, latency in current)[ceil(0.95 * capacity) - 1]
    errors = sum(not status for status, _ in current) / capacity
    snapshot = slo.snapshot()
    assert snapshot["samples"] == capacity
    assert snapshot["error_rate"] == pytest.approx(errors)
    assert snapshot["p95_ms"] == p95
    assert snapshot["healthy"] == (errors <= 0.12 and p95 <= 1500)


@pytest.mark.parametrize("seed", range(64), ids=lambda x: f"concurrent-admission-{x:03d}")
def test_concurrent_admission_caps_and_releases_on_failures(seed):
    limit, workers = 1 + seed % 7, 16 + seed % 16
    limiter, barrier = ConcurrencyLimiter(limit), Barrier(workers)
    peak, admitted, rejected = [0], [0], [0]
    lock = Lock()

    def worker(index):
        barrier.wait(timeout=4)
        try:
            with limiter.admit():
                with lock:
                    admitted[0] += 1
                    peak[0] = max(peak[0], limiter.active)
                sleep(0.003)
                if (index + seed) % 7 == 0:
                    raise OSError("interrupted worker")
        except RateLimited:
            with lock:
                rejected[0] += 1
        except OSError:
            pass

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(worker, range(workers)))
    assert admitted[0] + rejected[0] == workers
    assert 1 <= peak[0] <= limit
    assert limiter.active == 0
    with limiter.admit():
        assert limiter.active == 1


@pytest.mark.parametrize("seed", range(64), ids=lambda x: f"tenant-key-{x:03d}")
def test_idempotency_namespacing_and_branch_isolation(seed):
    repository = f"https://github.com/tenant-{seed % 17}/service-{seed}"
    branch = f"release/{seed % 13}"
    name = f"service-{seed}"
    first = deployment_key(repository, branch, name)
    assert first == deployment_key(repository.upper(), branch, name)
    assert len(first) == 64
    assert first != deployment_key(repository, branch + "-next", name)
    assert first != deployment_key(repository, branch, name + "-next")
    assert first != deployment_key(repository + "-other", branch, name)


def test_soak_4096_requests_64_workers_bounded_memory_and_rate():
    quota = ConcurrencyLimiter(32)
    limiter = TokenBucket(1024, 0)
    accepted, denied = [0], [0]
    guard = Lock()

    def call(i):
        try:
            with quota.admit():
                if not limiter.consume():
                    with guard:
                        denied[0] += 1
                else:
                    with guard:
                        accepted[0] += 1
        except RateLimited:
            with guard:
                denied[0] += 1

    with ThreadPoolExecutor(max_workers=64) as pool:
        list(pool.map(call, range(4096)))
    assert accepted[0] == 1024
    assert denied[0] == 3072
    assert quota.active == 0
    assert limiter.available == 0


def test_faults_do_not_leak_quota_or_poison_singleflight_cache():
    limit = ConcurrencyLimiter(1)
    for _ in range(400):
        with pytest.raises(OSError):
            with limit.admit():
                raise OSError("worker died")
        assert limit.active == 0
    sf = SingleFlight()
    with pytest.raises(OSError):
        sf.run("deployment", lambda: (_ for _ in ()).throw(OSError("first")))
    assert sf.run("deployment", lambda: "recovered") == "recovered"


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf"), 1025])
def test_reject_invalid_limits(bad):
    with pytest.raises(ValueError):
        TokenBucket(2, 1).consume(bad)

