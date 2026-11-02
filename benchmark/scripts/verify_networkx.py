"""Cross-check update decisions and topological orders against NetworkX."""

import json
import os
import random
import subprocess

import networkx as nx

from build import ROOT
from workloads import canonical


def main():
    exe = (
        ROOT
        / "benchmark/build"
        / ("topo_bench.exe" if os.name == "nt" else "topo_bench")
    )
    out = ROOT / "benchmark/_cache/networkx"
    out.mkdir(parents=True, exist_ok=True)
    cases = []
    sample = [(0, 1), (0, 2), (2, 3), (2, 4), (1, 5), (3, 5), (4, 5), (5, 6)]
    cases.append(
        (7, list(range(7)), sample, [(1, 4), (4, 3), (6, 2), (3, 3), (1, 4), (0, 6)])
    )
    for seed in range(30):
        rng = random.Random(seed)
        n = 2 + seed
        order = list(range(n))
        rng.shuffle(order)
        edges = [
            (order[i], order[j])
            for i in range(n)
            for j in range(i + 1, n)
            if rng.random() < 0.1
        ]
        updates = [(rng.randrange(n), rng.randrange(n)) for _ in range(300)]
        cases.append((n, order, edges, updates))
    checks = 0
    decisions = {"accepted": 0, "cycle": 0, "duplicate": 0}
    for case_id, (n, order, edges, updates) in enumerate(cases):
        path = out / f"{case_id}.dag"
        path.write_bytes(canonical(n, order, edges, updates))
        folder = out / str(case_id)
        subprocess.run(
            [str(exe), "--input", str(path), "--out", str(folder), "--mode", "trace"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        records = [
            json.loads(line)
            for line in (folder / "trace.jsonl").read_text().splitlines()
        ]
        graphs = {
            name: nx.DiGraph()
            for name in ["kahn_recompute", "kahn_guarded", "incremental_rpo"]
        }
        for g in graphs.values():
            g.add_nodes_from(range(n))
            g.add_edges_from(edges)
        for r in records:
            g = graphs[r["algorithm"]]
            u, v = r["u"], r["v"]
            if g.has_edge(u, v):
                expected = "duplicate"
            else:
                g.add_edge(u, v)
                expected = "accepted" if nx.is_directed_acyclic_graph(g) else "cycle"
                if expected == "cycle":
                    g.remove_edge(u, v)
            assert expected == r["status"], (case_id, r)
            result = r["order"]
            assert len(result) == n and set(result) == set(range(n))
            pos = {v: i for i, v in enumerate(result)}
            assert all(pos[u] < pos[v] for u, v in g.edges), (case_id, r)
            checks += 1
            decisions[expected] += 1
    report = dict(
        passed=True,
        networkx_version=nx.__version__,
        cases=len(cases),
        transition_order_checks=checks,
        decisions=decisions,
    )
    dest = ROOT / "benchmark/tests/validation_networkx.json"
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
