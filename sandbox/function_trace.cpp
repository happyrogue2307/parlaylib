#include <cxxabi.h>
#include <dlfcn.h>
#include <pthread.h>
#include <time.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>

#define NO_INSTRUMENT __attribute__((no_instrument_function))

static NO_INSTRUMENT void record_event(const char* event,
    void* function,
    void* caller) {

    uint64_t thread_id = 0;
    pthread_threadid_np(nullptr, &thread_id);

    timespec timestamp;
    clock_gettime(CLOCK_MONOTONIC_RAW, &timestamp);

    Dl_info symbol_info;
    const bool found =
        dladdr(function, &symbol_info) != 0 &&
        symbol_info.dli_sname != nullptr;

    const char* mangled_name =
        found ? symbol_info.dli_sname : "<unknown>";

    int demangle_status = -1;
    char* demangled_name = nullptr;

    if (found) {
        demangled_name = abi::__cxa_demangle(
            mangled_name,
            nullptr,
            nullptr,
            &demangle_status);
    }

    const char* display_name =
        demangle_status == 0 && demangled_name != nullptr
            ? demangled_name
            : mangled_name;

    std::uintptr_t symbol_offset = 0;
    if (found && symbol_info.dli_saddr != nullptr) {
        symbol_offset =
            reinterpret_cast<std::uintptr_t>(function) -
            reinterpret_cast<std::uintptr_t>(symbol_info.dli_saddr);
    }

    std::fprintf(
        stderr,
        "%lld.%09ld thread=%llu %-5s %s+0x%llx "
        "function=%p caller=%p\n",
        static_cast<long long>(timestamp.tv_sec),
        timestamp.tv_nsec,
        static_cast<unsigned long long>(thread_id),
        event,
        display_name,
        static_cast<unsigned long long>(symbol_offset),
        function,
        caller);

    std::free(demangled_name);
}

extern "C" NO_INSTRUMENT void __cyg_profile_func_enter(
    void* function,
    void* caller) {

    record_event("ENTER", function, caller);
}

extern "C" NO_INSTRUMENT void __cyg_profile_func_exit(
    void* function,
    void* caller) {

    record_event("EXIT", function, caller);
}