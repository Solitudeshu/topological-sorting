"""Audit raw rows, calculate paired statistics, and publish CSVs without manual edits."""

import argparse
import csv
import json
import statistics as st
from collections import defaultdict

from build import ROOT

KEYS = ["benchmark", "family", "n", "m0", "q", "algorithm"]
METRICS = [
    "vertices",
    "edge_checks",
    "window_len",
    "order_writes",
    "pos_writes",
    "changed_positions",
    "recomputations",
    "max_frontier",
]


def quantile(xs, p):
    xs = sorted(xs)
    index = (len(xs) - 1) * p
    lo = int(index)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] * (hi - index) + xs[hi] * (index - lo) if hi != lo else xs[lo]


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def summarize(profile):
    dest = ROOT / "benchmark/results" / profile
    manifest = json.loads((dest / "manifest.json").read_text())
    env = json.loads((dest / "environment.json").read_text(encoding="utf-8"))
    groups = defaultdict(list)
    paired = defaultdict(dict)
    per_seed = []
    total_checks = 0
    attempts = 0
    timing_rows = 0
    instrumented_rows = 0
    for spec in manifest:
        folder = dest / "raw" / spec["workload"]
        v = json.loads((folder / "validation.json").read_text())
        assert v["passed"]
        total_checks += v["checks"]
        attempts += spec["q"]
        timings = read_csv(folder / "timing.csv")
        work = read_csv(folder / "work.csv")
        timing_rows += len(timings)
        instrumented_rows += len(work)
        algorithms = sorted({r["algorithm"] for r in timings})
        assert len(algorithms) == (3 if spec["q"] else 2)
        for alg in algorithms:
            ts = [r for r in timings if r["algorithm"] == alg]
            ws = [r for r in work if r["algorithm"] == alg]
            assert len(ts) == env["repeats"] and {int(r["repeat"]) for r in ts} == set(
                range(env["repeats"])
            )
            assert len(ws) == (spec["q"] or 1)
            assert all(r["status"] == "ok" for r in ts)
            for r in ts:
                assert (
                    int(r["accepted"]) == v["accepted"]
                    and int(r["cycles"]) == v["cycles"]
                )
            times = [int(r["elapsed_ns"]) / int(r["batch"]) for r in ts]
            unit_times = [x / (spec["q"] or 1) for x in times]
            row = {
                k: spec[k]
                for k in [
                    "benchmark",
                    "family",
                    "n",
                    "m0",
                    "q",
                    "seed",
                    "density",
                    "workload",
                ]
            }
            row.update(
                algorithm=alg,
                median_ns=st.median(unit_times),
                q25_repeat_ns=quantile(unit_times, 0.25),
                q75_repeat_ns=quantile(unit_times, 0.75),
                total_median_ns=st.median(times),
                setup_median_ns=st.median(int(r["setup_ns"]) for r in ts),
                aux_payload_bytes=max(int(r["aux_payload_peak_bytes"]) for r in ws),
                graph_payload_bytes=max(int(r["graph_payload_bytes"]) for r in ws),
                accepted=v["accepted"],
                cycles=v["cycles"],
            )
            for metric in METRICS:
                row[metric] = st.mean(int(r[metric]) for r in ws)
            per_seed.append(row)
            groups[tuple(row[k] for k in KEYS)].append(row)
            paired[spec["workload"]][alg] = row
            if alg == "incremental_rpo":
                if spec["family"] == "local_small":
                    assert max(int(r["window_len"]) for r in ws) / spec["n"] <= 0.01
                    assert max(int(r["vertices"]) for r in ws) / spec["n"] <= 0.01
                elif spec["family"] == "local_large":
                    assert min(int(r["window_len"]) for r in ws) / spec["n"] >= 0.5
                    assert min(int(r["vertices"]) for r in ws) / spec["n"] >= 0.25
                elif spec["family"] == "forward":
                    assert all(
                        int(r["vertices"]) == 0 and int(r["order_writes"]) == 0
                        for r in ws
                    )
                elif spec["family"] == "cycle":
                    assert all(
                        r["status"] == "cycle" and int(r["order_writes"]) == 0
                        for r in ws
                    )
                elif spec["family"] == "window_only":
                    assert all(
                        int(r["vertices"]) == 1 and int(r["edge_checks"]) == 0
                        for r in ws
                    )
    summaries = []
    numeric = [
        "median_ns",
        "total_median_ns",
        "setup_median_ns",
        "aux_payload_bytes",
        "graph_payload_bytes",
        "accepted",
        "cycles",
    ] + METRICS
    for key, rows in sorted(groups.items()):
        r = dict(zip(KEYS, key))
        r["seeds"] = len(rows)
        for metric in numeric:
            r[metric] = st.median(x[metric] for x in rows)
        r["q25_seed_ns"] = quantile([x["median_ns"] for x in rows], 0.25)
        r["q75_seed_ns"] = quantile([x["median_ns"] for x in rows], 0.75)
        summaries.append(r)
    speed_seeds = []
    speed_groups = defaultdict(list)
    for name, rows in paired.items():
        if "incremental_rpo" not in rows:
            continue
        inc = rows["incremental_rpo"]
        for base in ["kahn_recompute", "kahn_guarded"]:
            r = {k: inc[k] for k in ["family", "n", "m0", "q", "seed"]}
            r.update(baseline=base, speedup=rows[base]["median_ns"] / inc["median_ns"])
            speed_seeds.append(r)
            speed_groups[
                tuple(r[k] for k in ["family", "n", "m0", "q", "baseline"])
            ].append(r["speedup"])
    speed = []
    for key, values in sorted(speed_groups.items()):
        r = dict(zip(["family", "n", "m0", "q", "baseline"], key))
        r.update(
            median_speedup=st.median(values),
            q25=quantile(values, 0.25),
            q75=quantile(values, 0.75),
            seeds=len(values),
        )
        speed.append(r)
    write_csv(dest / "summary/per_seed.csv", per_seed)
    write_csv(dest / "summary/summary.csv", summaries)
    write_csv(dest / "summary/speedups_per_seed.csv", speed_seeds)
    write_csv(dest / "summary/speedups.csv", speed)
    validation = dict(
        passed=True,
        workloads=len(manifest),
        static_workloads=sum(not s["q"] for s in manifest),
        dynamic_workloads=sum(bool(s["q"]) for s in manifest),
        workload_result_checks=total_checks,
        distinct_update_attempts=attempts,
        timing_rows=timing_rows,
        instrumented_rows=instrumented_rows,
        measured_case_thresholds_passed=True,
    )
    (dest / "summary/validation_summary.json").write_text(
        json.dumps(validation, indent=2), encoding="utf-8"
    )
    print(json.dumps(validation))
    return summaries, speed


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--profile", choices=["quick", "full"], default="full")
    summarize(p.parse_args().profile)
