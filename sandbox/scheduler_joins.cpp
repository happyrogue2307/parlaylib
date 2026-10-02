#include "parlay/parallel.h"
#include <os/signpost.h>

using namespace parlay;

extern "C" void __cyg_profile_func_enter(
    void* function,
    void* caller);

extern "C" void __cyg_profile_func_exit(
    void* function,
    void* caller);

int main() {
    long long val = 0;
    int lval = 0, rval = 0;
    int lval1 = 0, lval2 = 0;
    auto sub_left1 = [&] {
        for(int i = 1; i <= 1E8; i++) {
            lval1++;
        }
    };
    auto sub_left2 = [&] {
        for(int i = 1; i <= 1E8; i++) {
            lval2++;
        }
    };
    auto left = [&] {
        // Do Nothing
    };

    auto right = [&] {
        for (int i = 0; i < 1E9; ++i){
            rval += 1;
        }
    };

    par_do(left, right);
    val += lval + rval;
    std::cout << val << "\n";
}