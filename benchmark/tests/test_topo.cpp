#include "topo.hpp"

#include <fstream>
#include <iostream>
#include <random>

using namespace topo;

std::uint64_t static_checks = 0, update_checks = 0, invalid_checks = 0, dag_inputs = 0;

void require(bool x, const char* message) {
    if (!x) {
        throw std::runtime_error(message);
    }
}

void static_test(const Graph& g, bool expected) {
    Stats s, t;
    auto a = kahn<true>(g, s);
    auto b = dfs<true>(g, t);
    require(a.dag == expected && b.dag == expected, "static cycle mismatch");
    if (expected) {
        require(valid(g, a.order) && valid(g, b.order), "invalid static order");
    }
    static_checks += 2;
}

void one_update(Dynamic& d, int u, int v) {
    auto before = d.order;
    auto bp = d.pos;
    auto adj = d.g.adj;
    auto m = d.g.m;
    Status expected = d.g.has(u, v)        ? Status::duplicate
                      : reaches(d.g, v, u) ? Status::cycle
                                           : Status::accepted;
    Dynamic plain = d;
    Stats ignored;
    auto plain_got = plain.add<false>(u, v, ignored);
    Stats s;
    auto got = d.add<true>(u, v, s);
    require(plain_got == got && plain.order == d.order && plain.g.adj == d.g.adj &&
                plain.pos == d.pos,
            "instrumentation changed semantics");
    require(got == expected, "update decision mismatch");
    if (got == Status::accepted) {
        require(d.g.m == m + 1 && d.g.has(u, v), "edge was not inserted");
    } else {
        require(d.g.adj == adj && d.g.m == m && d.order == before && d.pos == bp,
                "rejection changed semantic state");
    }
    require(d.invariant() && plain.invariant(), "dynamic invariant failed");
    update_checks += 2;
}

int main(int argc, char** argv) try {
    Graph empty;
    static_test(empty, true);
    Graph single(1);
    static_test(single, true);
    Graph chain(100000);
    for (int i = 0; i < 99999; ++i) {
        chain.append(i, i + 1);
    }
    static_test(chain, true);
    std::vector<std::pair<int, int>> possible;
    for (int u = 0; u < 4; ++u) {
        for (int v = 0; v < 4; ++v) {
            if (u != v) {
                possible.emplace_back(u, v);
            }
        }
    }
    for (unsigned mask = 0; mask < (1u << possible.size()); ++mask) {
        Graph g(4);
        for (unsigned j = 0; j < possible.size(); ++j) {
            if (mask & (1u << j)) {
                g.append(possible[j].first, possible[j].second);
            }
        }
        bool ok = oracle_dag(g);
        static_test(g, ok);
        if (!ok) {
            continue;
        }
        ++dag_inputs;
        Stats s;
        auto initial = kahn<false>(g, s).order;
        for (int u = 0; u < 4; ++u) {
            for (int v = 0; v < 4; ++v) {
                for (Method method : {Method::recompute, Method::guarded, Method::incremental}) {
                    Dynamic d(g, initial, method);
                    one_update(d, u, v);
                }
            }
        }
    }
    require(dag_inputs == 543, "exhaustive DAG count mismatch");
    Graph sample(7);
    for (auto e : std::vector<std::pair<int, int>>{
             {0, 1}, {0, 2}, {2, 3}, {2, 4}, {1, 5}, {3, 5}, {4, 5}, {5, 6}}) {
        sample.append(e.first, e.second);
    }
    std::vector<int> initial(7);
    std::iota(initial.begin(), initial.end(), 0);
    for (Method method : {Method::recompute, Method::guarded, Method::incremental}) {
        Dynamic d(sample, initial, method);
        for (auto e :
             std::vector<std::pair<int, int>>{{1, 4}, {4, 3}, {6, 2}, {3, 3}, {1, 4}, {0, 6}}) {
            one_update(d, e.first, e.second);
        }
        for (auto e : std::vector<std::pair<int, int>>{{-1, 0}, {0, 7}}) {
            bool threw = false;
            try {
                Stats s;
                d.add<false>(e.first, e.second, s);
            } catch (const std::out_of_range&) {
                threw = true;
            }
            require(threw, "invalid vertex not rejected");
            ++invalid_checks;
        }
    }
    for (unsigned seed = 0; seed < 100; ++seed) {
        std::mt19937 rng(seed);
        int n = 2 + static_cast<int>(rng() % 49);
        Graph g(n);
        std::vector<int> order(n);
        std::iota(order.begin(), order.end(), 0);
        std::shuffle(order.begin(), order.end(), rng);
        Dynamic a(g, order, Method::recompute), b(g, order, Method::guarded),
            c(g, order, Method::incremental);
        for (int i = 0; i < 500; ++i) {
            int u = rng() % n, v = rng() % n;
            one_update(a, u, v);
            one_update(b, u, v);
            one_update(c, u, v);
            require(a.g.adj == c.g.adj && b.g.adj == c.g.adj, "graphs diverged");
        }
    }
    // Small search, full window; also verify timestamp wraparound.
    Graph g(1000);
    std::vector<int> order(1000);
    std::iota(order.begin(), order.end(), 0);
    Dynamic d(g, order, Method::incremental);
    d.stamp = UINT32_MAX;
    Stats s;
    require(d.add<true>(999, 0, s) == Status::accepted, "window fixture rejected");
    require(s.vertices == 1 && s.window_len == 1000 && s.order_writes == 1000 && d.invariant(),
            "window counters mismatch");
    ++update_checks;
    std::string json =
        "{\"passed\":true,\"static_result_checks\":" + std::to_string(static_checks) +
        ",\"dynamic_transition_checks\":" + std::to_string(update_checks) +
        ",\"invalid_vertex_checks\":" + std::to_string(invalid_checks) +
        ",\"exhaustive_graphs_n4\":4096,\"exhaustive_dags_n4\":543,\"random_seeds\":100,\"long_"
        "chain_n\":100000}";
    std::cout << json << '\n';
    if (argc > 1) {
        std::ofstream f(argv[1]);
        f << json << '\n';
    }
    return 0;
} catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
}
