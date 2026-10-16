#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <optional>
#include <random>
#include <sstream>
#include <string>
#include <vector>

#include <parlay/primitives.h>
#include <parlay/sequence.h>
#include <parlay/random.h>
#include <parlay/scheduler.h>
#include "../examples/delaunay.h"

// **************************************************************
//  Test out how "non-greedy" the delaunay program and a parallel
//  reduce are, averaged over several runs, for a range of input
//  sizes and processor counts.
//
//  Usage: delaunay_test [--procs 4,8,16,32,64] [--nmin 100] [--nmax 1e7]
//                       [--runs 5] [--algos delaunay,reduce]
//                       [--out sandbox/trace_results] [--grid]
//
//  Appends one row per run to <out>/runs.csv. With --grid, the full
//  traces are also written to <out>/raw/<algo>/p<P>/n<n>/run<r>.*.txt
// **************************************************************

// Max of the points in [l, r) by x, breaking ties by y.
point reduce_max(const parlay::sequence<point>& points, long l, long r) {
    auto points_max = [] (point p1, point p2) {
        if (p1.x > p2.x) {
            return p1;
        } else if (p1.x < p2.x) {
            return p2;
        } else {
            return p1.y >= p2.y ? p1 : p2;
        }
    };
    long len = r - l;
    long block_size = 10;
    if (len == 0) return point{-1, std::numeric_limits<real>::lowest(), std::numeric_limits<real>::lowest()};
    if (len <= block_size) {
        point v = points[l];
        for (long i = l + 1; i < r; i++)
            v = points_max(v, points[i]);
        return v;
    }

    point L, R;
    long mid = l + len/2;
    parlay::par_do_jc([&] {L = reduce_max(points, l, mid);},
                      [&] {R = reduce_max(points, mid, r);});
    return points_max(L, R);
}

std::vector<std::string> split(const std::string& s) {
    std::vector<std::string> out;
    std::stringstream ss(s);
    for (std::string item; std::getline(ss, item, ',');) out.push_back(item);
    return out;
}

int main(int argc, char* argv[]) {
    std::vector<int> procs = {4, 8, 16, 32, 64};
    long nmin = 100, nmax = 10'000'000;
    int runs = 5;
    std::vector<std::string> algos = {"delaunay", "reduce"};
    std::filesystem::path out_dir = "sandbox/trace_results";
    bool grid = false;

    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        auto next = [&] { if (i + 1 >= argc) { std::cerr << arg << " needs a value\n"; std::exit(1); } return std::string(argv[++i]); };
        if (arg == "--procs") { procs.clear(); for (auto& p : split(next())) procs.push_back(std::stoi(p)); }
        else if (arg == "--nmin") nmin = static_cast<long>(std::stod(next()));
        else if (arg == "--nmax") nmax = static_cast<long>(std::stod(next()));
        else if (arg == "--runs") runs = std::stoi(next());
        else if (arg == "--algos") algos = split(next());
        else if (arg == "--out") out_dir = next();
        else if (arg == "--grid") grid = true;
        else { std::cerr << "unknown argument " << arg << "\n"; return 1; }
    }

    std::filesystem::create_directories(out_dir);
    const auto csv_path = out_dir / "runs.csv";
    const bool new_csv = !std::filesystem::exists(csv_path);
    std::ofstream csv(csv_path, std::ios::app);
    if (new_csv) csv << "algo,p,n,run,workers,columns,elapsed_ns,steal_while_ready,min_steal_ready\n";
    parlay::trace_write_files = grid;

    for (long n = nmin; n <= nmax; n *= 10) {
        // Every parlay::sequence constructor touches the current scheduler, so
        // building the points outside of any scheduler would start parlay's
        // default scheduler, whose workers then compete for cores with the
        // measured one. Build them in an untraced (trace_base is empty)
        // scheduler that is gone before the measured runs start.
        std::optional<parlay::sequence<point>> points_storage;
        parlay::execute_with_scheduler(std::thread::hardware_concurrency(), [&] {
            parlay::random_generator gen(0);
            std::uniform_real_distribution<real> dis(0.0,1.0);

            // generate n random points in a unit square
            points_storage.emplace(parlay::tabulate(n, [&] (point_id i) -> point {
                auto r = gen[i];
                return point{i, dis(r), dis(r)};}));
        });
        const auto& points = *points_storage;

        for (int p : procs) {
            for (const auto& algo : algos) {
                for (int run = 1; run <= runs; run++) {
                    if (parlay::internal::scheduler_type::get_current_scheduler() != nullptr)
                        std::cerr << "warning: default scheduler is running alongside the measured one\n";

                    auto run_dir = out_dir / "raw" / algo / ("p" + std::to_string(p)) / ("n" + std::to_string(n));
                    if (grid) std::filesystem::create_directories(run_dir);
                    parlay::trace_base = (run_dir / ("run" + std::to_string(run))).string();

                    if (algo == "delaunay") {
                        parlay::execute_with_scheduler(p, [&] { auto result = delaunay(points); });
                    } else if (algo == "reduce") {
                        point result;
                        parlay::execute_with_scheduler(p, [&] { result = reduce_max(points, 0, n); });
                        if (run == 1) {
                            point expected = points[0];
                            for (long i = 1; i < n; i++)
                                if (points[i].x > expected.x || (points[i].x == expected.x && points[i].y > expected.y))
                                    expected = points[i];
                            if (result.id != expected.id)
                                std::cerr << "error: reduce returned point " << result.id << ", expected " << expected.id << "\n";
                        }
                    } else {
                        std::cerr << "unknown algo " << algo << "\n";
                        return 1;
                    }
                    parlay::trace_base.clear();

                    const auto& s = parlay::last_trace_summary;
                    csv << algo << ',' << p << ',' << n << ',' << run << ',' << s.workers << ',' << s.columns << ','
                        << s.elapsed_ns << ',' << s.steal_while_ready << ',' << s.min_steal_ready << '\n' << std::flush;
                    std::cout << algo << " p=" << p << " n=" << n << " run=" << run
                              << ": columns=" << s.columns
                              << " S*[ready>0]=" << s.steal_while_ready
                              << " min(S,ready)=" << s.min_steal_ready << std::endl;
                }
            }
        }
    }
}
