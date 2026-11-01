#pragma once
#include <algorithm>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace topo {
using Bytes = std::uint64_t;
struct Graph {
    std::vector<std::vector<int>> adj;
    std::uint64_t m = 0;
    explicit Graph(int n = 0) : adj(n) {}
    int size() const { return static_cast<int>(adj.size()); }
    void check(int u) const { if (u < 0 || u >= size()) throw std::out_of_range("vertex outside [0,n)"); }
    bool has(int u, int v) const {
        return std::find(adj[u].begin(), adj[u].end(), v) != adj[u].end();
    }
    void append(int u, int v) { adj[u].push_back(v); ++m; }
    void undo_append(int u) { adj[u].pop_back(); --m; }
    Bytes payload() const {
        Bytes b = adj.capacity() * sizeof(std::vector<int>);
        for (const auto& a : adj) b += a.capacity() * sizeof(int);
        return b;
    }
};
struct Stats {
    std::uint64_t vertices = 0, edge_checks = 0, window_len = 0;
    std::uint64_t order_writes = 0, pos_writes = 0, changed_positions = 0, recomputations = 0;
    std::uint64_t max_frontier = 0;
    Bytes aux_peak = 0;
};
struct Result { bool dag; std::vector<int> order; };
struct Frame { int vertex; std::size_t next; };

template<bool Count> Result kahn(const Graph& g, Stats& s) {
    const int n = g.size();
    std::vector<int> degree(n, 0), queue, out;
    queue.reserve(n); out.reserve(n);
    for (int u = 0; u < n; ++u) for (int v : g.adj[u]) {
        ++degree[v]; if constexpr(Count) ++s.edge_checks;
    }
    for (int v = 0; v < n; ++v) if (!degree[v]) queue.push_back(v);
    std::size_t head = 0;
    if constexpr(Count) s.max_frontier = queue.size();
    while (head < queue.size()) {
        int u = queue[head++]; out.push_back(u);
        if constexpr(Count) { ++s.vertices; ++s.order_writes; }
        for (int v : g.adj[u]) {
            if constexpr(Count) ++s.edge_checks;
            if (--degree[v] == 0) queue.push_back(v);
        }
        if constexpr(Count) s.max_frontier = std::max<std::uint64_t>(s.max_frontier, queue.size()-head);
    }
    if constexpr(Count) s.aux_peak = (degree.capacity()+queue.capacity()+out.capacity())*sizeof(int);
    bool ok = static_cast<int>(out.size()) == n;
    return {ok, std::move(out)};
}

template<bool Count> Result dfs(const Graph& g, Stats& s) {
    const int n = g.size();
    std::vector<std::uint8_t> color(n, 0);
    std::vector<int> out; out.reserve(n);
    std::vector<Frame> stack;
    auto memory = [&] {
        if constexpr(Count) s.aux_peak = color.capacity()*sizeof(std::uint8_t)
            + out.capacity()*sizeof(int) + stack.capacity()*sizeof(Frame);
    };
    for (int root = 0; root < n; ++root) {
        if (color[root]) continue;
        color[root] = 1; stack.push_back({root,0});
        if constexpr(Count) ++s.vertices;
        while (!stack.empty()) {
            if constexpr(Count) s.max_frontier = std::max<std::uint64_t>(s.max_frontier, stack.size());
            auto& f = stack.back();
            int u = f.vertex;
            if (f.next == g.adj[u].size()) {
                color[u] = 2; out.push_back(u); stack.pop_back();
                if constexpr(Count) ++s.order_writes;
            } else {
                int v = g.adj[u][f.next++];
                if constexpr(Count) ++s.edge_checks;
                if (color[v] == 1) { memory(); return {false, std::move(out)}; }
                if (!color[v]) {
                    color[v] = 1; stack.push_back({v,0});
                    if constexpr(Count) ++s.vertices;
                }
            }
        }
    }
    std::reverse(out.begin(),out.end());
    if constexpr(Count) s.order_writes += out.size()/2*2;
    memory();
    return {true,std::move(out)};
}

inline bool valid(const Graph& g, const std::vector<int>& order) {
    if (order.size() != g.adj.size()) return false;
    std::vector<int> pos(g.size(),-1);
    for (int i=0;i<g.size();++i) {
        int v=order[i]; if(v<0 || v>=g.size() || pos[v]!=-1) return false; pos[v]=i;
    }
    for(int u=0;u<g.size();++u) for(int v:g.adj[u]) if(pos[u]>=pos[v]) return false;
    return true;
}
// Independent oracle: reachability, not indegree or the measured bounded DFS.
inline bool reaches(const Graph& g,int source,int target) {
    if(source==target) return true;
    std::vector<std::uint8_t> seen(g.size(),0);
    std::vector<int> queue{source}; seen[source]=1;
    for(std::size_t p=0;p<queue.size();++p) for(int v:g.adj[queue[p]]) {
        if(v==target) return true;
        if(!seen[v]) {seen[v]=1;queue.push_back(v);}
    }
    return false;
}
inline bool oracle_dag(const Graph& g) {
    for(int u=0;u<g.size();++u) for(int v:g.adj[u]) if(reaches(g,v,u)) return false;
    return true;
}
enum class Status { accepted, cycle, duplicate };
inline const char* status_name(Status x) {
    return x==Status::accepted?"accepted":x==Status::cycle?"cycle":"duplicate";
}
enum class Method { recompute, guarded, incremental };
inline const char* method_name(Method x) {
    return x==Method::recompute?"kahn_recompute":x==Method::guarded?"kahn_guarded":"incremental_rpo";
}
struct Dynamic {
    Graph g;
    std::vector<int> order,pos;
    Method method;
    std::vector<std::uint32_t> mark;
    std::uint32_t stamp=0;
    std::vector<Frame> stack;
    std::vector<int> post,buffer;
    Dynamic(const Graph& input,const std::vector<int>& initial,Method m)
        : g(input),order(initial),pos(input.size()),method(m) {
        if(!valid(g,order)) throw std::invalid_argument("invalid initial order");
        for(int i=0;i<g.size();++i) pos[order[i]]=i;
        if(m==Method::incremental) mark.resize(g.size(),0);
    }
    Bytes payload() const {
        return (order.capacity()+pos.capacity()+post.capacity()+buffer.capacity())*sizeof(int)
            + mark.capacity()*sizeof(std::uint32_t) + stack.capacity()*sizeof(Frame);
    }
    bool invariant() const {
        if(!valid(g,order) || pos.size()!=order.size()) return false;
        for(int i=0;i<g.size();++i) if(pos[order[i]]!=i) return false;
        return true;
    }
    // novel=true is reserved for prevalidated benchmark files. Public/default API checks duplicates.
    template<bool Count> Status add(int u,int v,Stats& s,bool novel=false) {
        g.check(u); g.check(v);
        if constexpr(Count) s.aux_peak=payload();
        if(u==v) return Status::cycle;
        if(!novel && g.has(u,v)) return Status::duplicate;
        if(method!=Method::recompute && pos[u]<pos[v]) {
            g.append(u,v); return Status::accepted;
        }
        if(method!=Method::incremental) {
            g.append(u,v);
            Stats t; auto r=kahn<Count>(g,t);
            if constexpr(Count) {
                s.vertices=t.vertices; s.edge_checks=t.edge_checks; s.order_writes=t.order_writes;
                s.max_frontier=t.max_frontier; s.recomputations=1;
                s.aux_peak=std::max(s.aux_peak,payload()+t.aux_peak);
            }
            if(!r.dag) {g.undo_append(u);return Status::cycle;}
            if constexpr(Count) for(int i=0;i<g.size();++i) s.changed_positions+=(pos[r.order[i]]!=i);
            order=std::move(r.order);
            for(int i=0;i<g.size();++i) pos[order[i]]=i;
            if constexpr(Count) s.pos_writes=g.size();
            return Status::accepted;
        }
        const int left=pos[v],right=pos[u];
        if constexpr(Count) s.window_len=right-left+1;
        if(++stamp==0) {std::fill(mark.begin(),mark.end(),0);stamp=1;}
        stack.clear(); post.clear(); buffer.clear();
        mark[v]=stamp; stack.push_back({v,0});
        if constexpr(Count) ++s.vertices;
        while(!stack.empty()) {
            if constexpr(Count) s.max_frontier=std::max<std::uint64_t>(s.max_frontier,stack.size());
            auto& f=stack.back(); int x=f.vertex;
            if(f.next==g.adj[x].size()) {post.push_back(x);stack.pop_back();continue;}
            int y=g.adj[x][f.next++];
            if constexpr(Count) ++s.edge_checks;
            if(y==u) {
                if constexpr(Count) s.aux_peak=std::max(s.aux_peak,payload());
                return Status::cycle;
            }
            if(pos[y]<=right && mark[y]!=stamp) {
                mark[y]=stamp;stack.push_back({y,0});
                if constexpr(Count) ++s.vertices;
            }
        }
        for(int i=left;i<=right;++i) if(mark[order[i]]!=stamp) buffer.push_back(order[i]);
        for(auto it=post.rbegin();it!=post.rend();++it) buffer.push_back(*it);
        if constexpr(Count) for(std::size_t k=0;k<buffer.size();++k) s.changed_positions+=(pos[buffer[k]]!=left+static_cast<int>(k));
        for(std::size_t k=0;k<buffer.size();++k) {
            int i=left+static_cast<int>(k); order[i]=buffer[k];pos[buffer[k]]=i;
            if constexpr(Count) {++s.order_writes;++s.pos_writes;}
        }
        g.append(u,v);
        if constexpr(Count) s.aux_peak=std::max(s.aux_peak,payload());
        return Status::accepted;
    }
};
}
