#include <iostream>
#include <string>
#include <random>

#include <parlay/primitives.h>
#include <parlay/sequence.h>
#include <parlay/random.h>
#include <parlay/scheduler.h>
#include "../examples/delaunay.h"

#define MEASURE_DELAUNAY false
// **************************************************************
//  Test out how "non-greedy" the delaunay program is.
// **************************************************************
int curr_n = 1;        
int instance_counter = 1;

int main(int argc, char* argv[]) {
    for(point_id n=100; n <= 1E4; n*=10) {
        parlay::random_generator gen(0);
        std::uniform_real_distribution<real> dis(0.0,1.0);

        // generate n random points in a unit square

        auto points = parlay::tabulate(n, [&] (point_id i) -> point {
            auto r = gen[i];
            return point{i, dis(r), dis(r)};});
        
        parlay::sequence<tri> result;
        parlay::sequence<long long> average_non_greediness;
        
        long long total_averages = 0;

    #if MEASURE_AVERAGE_STEAL_TIME
        for (int i=0; i < 5; i++) {
            auto& curr_scheduler = parlay::internal::get_current_scheduler();
            auto average_steal_time = curr_scheduler.total_steal_time.load()/curr_scheduler.num_steal_attempts.load();
            total_averages += average_steal_time;
        }
    #endif

    #if MEASURE_DELAUNAY
        curr_n = n;
        instance_counter = 1; 
        int num_threads = std::stoi(getenv("PARLAY_NUM_THREADS"));
        parlay::execute_with_scheduler(num_threads, [&] { result = delaunay(points);});
    #else
        curr_n = n;
        instance_counter = 1;
        int num_threads = std::stoi(getenv("PARLAY_NUM_THREADS"));
        auto mini_reduce = [&] (auto&& self, int l, int r) -> point {
            auto points_max = [&] (point p1, point p2) {
                if(p1.x > p1.x) {
                    return p1;
                } else if (p1.x < p2.x) {
                    return p2;
                } else {
                    return p1.y >= p2.y ? p1 : p2;
                }
            };
            long len = r - l;
            using T = typename parlay::sequence<point>::value_type;
            long block_size = 10;
            if (len == 0) return point{-1, std::numeric_limits<float>::min(), std::numeric_limits<float>::min()};
            if (len <= block_size) {
              T v = points[0];
              for (long i=l; i < r; i++)
                v = points_max(v, points[i]);
              return v;
            }
        
            T L, R;
            parlay::par_do_jc([&] {L = self(self, 0, len/2);},
                           [&] {R = self(self, len/2, len);});
            return points_max(L,R);   
        
        };
        parlay::execute_with_scheduler(num_threads, [&] {point result = mini_reduce(mini_reduce, 0, n);});
    #endif

        
    #if MEASURE_AVERAGE_STEAL_TIME
        std::cout << "Time for n = " << n << ": " << total_averages/100 << "\n";
    #endif
    }
}
