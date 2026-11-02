#include "topo.hpp"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <random>

using namespace topo;

using Clock = std::chrono::steady_clock;
using Ns = std::chrono::nanoseconds;

volatile std::uint64_t sink = 0;

struct Input {
    Graph g;
    std::vector<int> initial;
    std::vector<std::pair<int, int>> updates;
};

Input read_input(const std::string& file) {
    std::ifstream f(file);
    std::string magic;
    int n;
    std::uint64_t m, q;
    if (!(f >> magic >> n >> m >> q) || magic != "TOPO_WORKLOAD_V1" || n < 0) {
        throw std::runtime_error("bad input header");
    }
    Input w{Graph(n), std::vector<int>(n), {}};
    for (int& v : w.initial) {
        if (!(f >> v)) {
            throw std::runtime_error("missing initial order");
        }
    }
    for (std::uint64_t i = 0; i < m; ++i) {
        int u, v;
        if (!(f >> u >> v)) {
            throw std::runtime_error("missing edge");
        }
        w.g.check(u);
        w.g.check(v);
        w.g.append(u, v);
    }
    for (std::uint64_t i = 0; i < q; ++i) {
        int u, v;
        if (!(f >> u >> v)) {
            throw std::runtime_error("missing update");
        }
        w.g.check(u);
        w.g.check(v);
        w.updates.emplace_back(u, v);
    }
    if (!valid(w.g, w.initial)) {
        throw std::runtime_error("initial order not valid");
    }
    for (int u = 0; u < n; ++u) {
        auto a = w.g.adj[u];
        std::sort(a.begin(), a.end());
        if (std::adjacent_find(a.begin(), a.end()) != a.end()) {
            throw std::runtime_error("duplicate initial edge");
        }
    }
    return w;
}

void consume(const std::vector<int>& order) {
    sink = sink + order.size() + (order.empty() ? 0 : order.front() + order.back());
}

void csv_header(std::ofstream& f) {
    f << "algorithm,update_id,u,v,status,vertices,edge_checks,window_len,"
         "order_writes,pos_writes,changed_positions,recomputations,"
         "max_frontier,aux_payload_peak_bytes,graph_payload_bytes\n";
}

void work_row(std::ofstream& f, const std::string& name, int id, int u, int v, Status status,
              const Stats& s, Bytes graph) {
    f << name << ',' << id << ',' << u << ',' << v << ',' << status_name(status) << ','
      << s.vertices << ',' << s.edge_checks << ',' << s.window_len << ',' << s.order_writes << ','
      << s.pos_writes << ',' << s.changed_positions << ',' << s.recomputations << ','
      << s.max_frontier << ',' << s.aux_peak << ',' << graph << '\n';
}

struct Validated {
    std::vector<Status> expected;
    std::uint64_t checks = 0, accepted = 0, cycles = 0, duplicates = 0;
};

Validated validate(const Input& w, bool allow_duplicates, std::ofstream* trace) {
    Validated r;
    if (w.updates.empty()) {
        Stats s, t;
        auto a = kahn<false>(w.g, s);
        auto b = dfs<false>(w.g, t);
        if (!a.dag || !b.dag || !valid(w.g, a.order) || !valid(w.g, b.order)) {
            throw std::runtime_error("static validation failed");
        }
        r.checks = 2;
        return r;
    }
    Graph oracle = w.g;
    Dynamic a(w.g, w.initial, Method::recompute), b(w.g, w.initial, Method::guarded),
        c(w.g, w.initial, Method::incremental);
    int id = 0;
    for (auto [u, v] : w.updates) {
        Status expected = oracle.has(u, v)        ? Status::duplicate
                          : reaches(oracle, v, u) ? Status::cycle
                                                  : Status::accepted;
        if (expected == Status::duplicate && !allow_duplicates) {
            throw std::runtime_error("timed workload contains a duplicate");
        }
        if (u == v && !allow_duplicates) {
            throw std::runtime_error("self loop reserved for correctness tests");
        }
        r.expected.push_back(expected);
        if (expected == Status::accepted) {
            oracle.append(u, v);
            ++r.accepted;
        } else if (expected == Status::cycle) {
            ++r.cycles;
        } else {
            ++r.duplicates;
        }
        for (Dynamic* d : {&a, &b, &c}) {
            auto old_order = d->order;
            auto old_pos = d->pos;
            auto old_m = d->g.m;
            Stats s;
            Status got = d->add<true>(u, v, s, !allow_duplicates);
            if (got != expected || !d->invariant() || d->g.adj != oracle.adj) {
                throw std::runtime_error("dynamic validation failed");
            }
            if (got != Status::accepted &&
                (d->order != old_order || d->pos != old_pos || d->g.m != old_m)) {
                throw std::runtime_error("rejection changed state");
            }
            ++r.checks;
            if (trace) {
                *trace << "{\"algorithm\":\"" << method_name(d->method) << "\",\"update\":" << id
                       << ",\"u\":" << u << ",\"v\":" << v << ",\"status\":\"" << status_name(got)
                       << "\",\"order\":[";
                for (std::size_t j = 0; j < d->order.size(); ++j) {
                    if (j) {
                        *trace << ',';
                    }
                    *trace << d->order[j];
                }
                *trace << "]}\n";
            }
        }
        ++id;
    }
    return r;
}

int main(int argc, char** argv) try {
    std::map<std::string, std::string> args;
    for (int i = 1; i < argc; i += 2) {
        if (i + 1 >= argc) {
            throw std::runtime_error("arguments are --key value pairs");
        }
        args[argv[i]] = argv[i + 1];
    }
    if (!args.count("--input")) {
        throw std::runtime_error(
            "required: --input FILE --out DIR [--repeats N --warmups N --mode all|validate|trace]");
    }
    const auto w = read_input(args.at("--input"));
    std::string out = args.count("--out") ? args["--out"] : "results";
    std::string mode = args.count("--mode") ? args["--mode"] : "all";
    std::filesystem::create_directories(out);
    std::ofstream trace;
    if (mode == "trace") {
        trace.open(out + "/trace.jsonl");
    }
    auto check_start = Clock::now();
    auto verified = validate(w, mode == "trace", mode == "trace" ? &trace : nullptr);
    auto validation_ns = std::chrono::duration_cast<Ns>(Clock::now() - check_start).count();
    {
        std::ofstream f(out + "/validation.json");
        f << "{\"passed\":true,\"checks\":" << verified.checks
          << ",\"accepted\":" << verified.accepted << ",\"cycles\":" << verified.cycles
          << ",\"duplicates\":" << verified.duplicates << ",\"validation_ns\":" << validation_ns
          << "}\n";
    }
    if (mode == "validate" || mode == "trace") {
        return 0;
    }
    if (mode != "all") {
        throw std::runtime_error("unknown mode");
    }
    const int repeats = args.count("--repeats") ? std::stoi(args["--repeats"]) : 10;
    const int warmups = args.count("--warmups") ? std::stoi(args["--warmups"]) : 3;
    if (repeats < 1 || warmups < 0) {
        throw std::runtime_error("invalid repetitions");
    }
    std::ofstream work(out + "/work.csv");
    csv_header(work);
    const bool dynamic = !w.updates.empty();
    std::vector<std::string> names =
        dynamic ? std::vector<std::string>{"kahn_recompute", "kahn_guarded", "incremental_rpo"}
                : std::vector<std::string>{"kahn_fifo", "dfs_iterative"};
    if (!dynamic) {
        for (const auto& name : names) {
            Stats s;
            auto r = name == "kahn_fifo" ? kahn<true>(w.g, s) : dfs<true>(w.g, s);
            if (!valid(w.g, r.order)) {
                throw std::runtime_error("instrumented order invalid");
            }
            work_row(work, name, -1, -1, -1, Status::accepted, s, w.g.payload());
        }
    } else {
        for (Method method : {Method::recompute, Method::guarded, Method::incremental}) {
            Dynamic d(w.g, w.initial, method);
            int id = 0;
            for (auto [u, v] : w.updates) {
                Stats s;
                auto status = d.add<true>(u, v, s, true);
                if (status != verified.expected[id]) {
                    throw std::runtime_error("instrumented status mismatch");
                }
                work_row(work, method_name(method), id, u, v, status, s, d.g.payload());
                ++id;
            }
            if (!d.invariant()) {
                throw std::runtime_error("instrumented final state invalid");
            }
        }
    }
    work.close();
    // No counters in the measured instantiations. Validation/work have already run separately.
    std::map<std::string, int> batches;
    for (const auto& name : names) {
        if (dynamic) {
            batches[name] = 1;
            continue;
        }
        Stats s;
        auto begin = Clock::now();
        auto r = name == "kahn_fifo" ? kahn<false>(w.g, s) : dfs<false>(w.g, s);
        auto elapsed =
            std::max<std::int64_t>(1, std::chrono::duration_cast<Ns>(Clock::now() - begin).count());
        consume(r.order);
        batches[name] = static_cast<int>(std::clamp<std::int64_t>(3000000 / elapsed, 1, 1000));
    }
    std::ofstream timing(out + "/timing.csv");
    timing << "algorithm,repeat,batch,setup_ns,elapsed_ns,accepted,cycles,status\n";
    std::mt19937 rng(7301);
    for (int rep = -warmups; rep < repeats; ++rep) {
        std::shuffle(names.begin(), names.end(), rng);
        for (const auto& name : names) {
            std::int64_t setup = 0, elapsed = 0;
            std::uint64_t accepted = 0, cycles = 0;
            if (dynamic) {
                Method method = name == "kahn_recompute" ? Method::recompute
                                : name == "kahn_guarded" ? Method::guarded
                                                         : Method::incremental;
                auto start = Clock::now();
                Dynamic d(w.g, w.initial, method);
                setup = std::chrono::duration_cast<Ns>(Clock::now() - start).count();
                Stats dummy;
                start = Clock::now();
                for (auto [u, v] : w.updates) {
                    auto st = d.add<false>(u, v, dummy, true);
                    accepted += (st == Status::accepted);
                    cycles += (st == Status::cycle);
                }
                elapsed = std::chrono::duration_cast<Ns>(Clock::now() - start).count();
                consume(d.order);
                if (!d.invariant() || accepted != verified.accepted || cycles != verified.cycles) {
                    throw std::runtime_error("timed final state mismatch");
                }
            } else {
                Result last{false, {}};
                Stats dummy;
                auto start = Clock::now();
                for (int j = 0; j < batches[name]; ++j) {
                    last = name == "kahn_fifo" ? kahn<false>(w.g, dummy) : dfs<false>(w.g, dummy);
                    consume(last.order);
                }
                elapsed = std::chrono::duration_cast<Ns>(Clock::now() - start).count();
                if (!last.dag || !valid(w.g, last.order)) {
                    throw std::runtime_error("timed static order invalid");
                }
            }
            if (rep >= 0) {
                timing << name << ',' << rep << ',' << batches[name] << ',' << setup << ','
                       << elapsed << ',' << accepted << ',' << cycles << ",ok\n";
            }
        }
    }
    std::cout << "ok n=" << w.g.size() << " m=" << w.g.m << " q=" << w.updates.size()
              << " checks=" << verified.checks << '\n';
    return 0;
} catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
}
