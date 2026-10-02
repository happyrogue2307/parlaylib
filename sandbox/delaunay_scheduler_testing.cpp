#include <iostream>
#include <string>
#include <random>

#include <parlay/primitives.h>
#include <parlay/sequence.h>
#include <parlay/random.h>
#include <parlay/scheduler.h>
#include "../examples/delaunay.h"

// **************************************************************
//  Test out how "non-greedy" the delaunay program is.
// **************************************************************

int main(int argc, char* argv[]) {
    for(point_id n=100; n <= 1E6; n*=10){
        parlay::random_generator gen(0);
        std::uniform_real_distribution<real> dis(0.0,1.0);

        // generate n random points in a unit square
        auto points = parlay::tabulate(n, [&] (point_id i) -> point {
          auto r = gen[i];
          return point{i, dis(r), dis(r)};});

        parlay::sequence<tri> result;
        parlay::sequence<long long> average_non_greediness;
        
        long long total_averages = 0;
        for (int i=0; i < 5; i++) {
            int num_threads = std::stoi(getenv("PARLAY_NUM_THREADS"));
            parlay::execute_with_scheduler(num_threads, delaunay(points));
        #if MEASURE_AVERAGE_STEAL_TIME
            auto& curr_scheduler = parlay::internal::get_current_scheduler();
            auto average_steal_time = curr_scheduler.total_steal_time.load()/curr_scheduler.num_steal_attempts.load();
            total_averages += average_steal_time;
        #endif
        }
    #if MEASURE_AVERAGE_STEAL_TIME
        std::cout << "Time for n = " << n << ": " << total_averages/100 << "\n";
    #endif
    }
}