"""Versioned, seeded synthetic DAGs; each canonical input is stored as deterministic gzip."""

import gzip
import hashlib
import json
import random
from pathlib import Path

VERSION = "dag-generators-v1"


def specifications(profile):
    cfg = json.loads(
        (
            Path(__file__).resolve().parents[1] / "configs" / f"{profile}.json"
        ).read_text()
    )
    seeds = cfg["seeds"]
    sizes = cfg["static_sizes"]
    specs = []
    for seed in seeds:
        for n in sizes:
            for family in ["chain", "sparse2", "sparse5", "layered", "disconnected"]:
                m = (
                    n - 1
                    if family == "chain"
                    else (2 * n if family in ["sparse2", "disconnected"] else 5 * n)
                )
                specs.append(
                    dict(
                        benchmark="static",
                        family=family,
                        n=n,
                        m_target=m,
                        seed=seed,
                        q_target=0,
                    )
                )
        for n in cfg["dense_sizes"]:
            for density in cfg["dense_densities"]:
                specs.append(
                    dict(
                        benchmark="static",
                        family="dense",
                        n=n,
                        m_target=int(density * n * (n - 1) / 2),
                        seed=seed,
                        q_target=0,
                    )
                )
        dynamic_sizes = cfg["dynamic_sizes"]
        for n in dynamic_sizes:
            for family in [
                "forward",
                "local_small",
                "local_large",
                "cycle",
                "window_only",
                "mixed",
            ]:
                specs.append(
                    dict(
                        benchmark="dynamic",
                        family=family,
                        n=n,
                        m_target=0 if family == "window_only" else 5 * n,
                        seed=seed,
                        q_target=cfg["dynamic_q"],
                    )
                )
        if cfg["density_experiment"]:
            for m in [2000, 49950, 149850]:
                for family in ["forward", "local_large", "cycle"]:
                    specs.append(
                        dict(
                            benchmark="dynamic",
                            family=family,
                            n=1000,
                            m_target=m,
                            seed=seed,
                            q_target=200,
                        )
                    )
    return specs


def generate(spec):
    n, target, seed, family = (spec[k] for k in ["n", "m_target", "seed", "family"])
    rng = random.Random(seed)
    order = list(range(n))
    rng.shuffle(order)
    edges, seen = [], set()

    def add(i, j):
        u, v = order[i], order[j]
        if (u, v) not in seen:
            edges.append((u, v))
            seen.add((u, v))

    block = min(8, max(2, n // 200))
    active = int(0.6 * n)
    if family in ["chain", "cycle"]:
        for i in range(n - 1):
            add(i, i + 1)
    elif family == "local_large":
        for i in range(active - 1):
            add(i, i + 1)
    elif family == "local_small":
        for start in range(0, n - block + 1, block):
            for i in range(start, start + block - 2):
                add(i, i + 1)
    attempts = 0
    while len(edges) < target:
        attempts += 1
        if attempts > max(100000, 100 * target):
            raise RuntimeError("infeasible edge target")
        limit = active if family == "local_large" else n
        i, j = rng.randrange(limit), rng.randrange(limit)
        if i == j:
            continue
        if i > j:
            i, j = j, i
        if family == "layered" and i * 10 // n == j * 10 // n:
            continue
        if family == "disconnected":
            half = int(0.45 * n)
            if not (
                i < half and j < half or half <= i < 2 * half and half <= j < 2 * half
            ):
                continue
        if family == "local_small" and i // block == j // block:
            continue
        add(i, j)
    updates = []
    attempted = set()

    def request(u, v):
        if u == v or (u, v) in seen or (u, v) in attempted:
            return False
        updates.append((u, v))
        attempted.add((u, v))
        return True

    q = spec["q_target"]
    if family == "local_small":
        starts = list(range(0, n - block + 1, block))
        rng.shuffle(starts)
        for start in starts[:q]:
            request(order[start + block - 1], order[start])
    elif family == "local_large":
        for i in range(min(q, n - active)):
            request(order[active + i], order[0])
    elif family == "window_only":
        for i in range(min(q, n // 5)):
            request(order[n - 1 - i], order[i])
    else:
        attempts = 0
        while len(updates) < q:
            attempts += 1
            if attempts > 1000000:
                raise RuntimeError("infeasible update target")
            if family == "forward":
                i, j = sorted(rng.sample(range(n), 2))
                request(order[i], order[j])
            elif family == "cycle":
                i = rng.randrange(max(1, n // 5))
                j = rng.randrange(4 * n // 5, n)
                request(order[j], order[i])
            elif family == "mixed":
                u, v = rng.sample(range(n), 2)
                request(u, v)
            elif q:
                raise ValueError(family)
    return order, edges, updates


def canonical(n, order, edges, updates):
    lines = [
        "TOPO_WORKLOAD_V1",
        f"{n} {len(edges)} {len(updates)}",
        " ".join(map(str, order)),
    ]
    lines.extend(f"{u} {v}" for u, v in edges)
    lines.extend(f"{u} {v}" for u, v in updates)
    return ("\n".join(lines) + "\n").encode("ascii")


def save(spec, directory):
    order, edges, updates = generate(spec)
    data = canonical(spec["n"], order, edges, updates)
    name = f"{spec['benchmark']}_{spec['family']}_n{spec['n']}_m{len(edges)}_q{len(updates)}_s{spec['seed']}"
    path = Path(directory) / (name + ".dag.gz")
    path.parent.mkdir(parents=True, exist_ok=True)
    compressed = gzip.compress(data, compresslevel=6, mtime=0)
    path.write_bytes(compressed)
    return (
        dict(
            spec,
            workload=name,
            n=spec["n"],
            m0=len(edges),
            q=len(updates),
            density=(
                2 * len(edges) / (spec["n"] * (spec["n"] - 1)) if spec["n"] > 1 else 0
            ),
            generator=VERSION,
            block_size=block_size(spec),
            sha256=hashlib.sha256(data).hexdigest(),
            compressed_sha256=hashlib.sha256(compressed).hexdigest(),
            input=path.name,
        ),
        data,
    )


def block_size(spec):
    return min(8, max(2, spec["n"] // 200)) if spec["family"] == "local_small" else None
