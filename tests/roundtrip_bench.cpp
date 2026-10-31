// Times the host-to-engine round trip for one block: submit work, wait for the
// engine's rendered output. Not a pass/fail test; it prints percentiles so a
// change to the engine's idle wait can show it did not slow blocks down.
//
//   mpvst_roundtrip_bench <engine> [frames] [blocks]
//
// "flat out" sends the next block as soon as the last returns. "paced" sleeps
// until the block's real-time slot, so the engine has been idle in between,
// which is what playback in a DAW looks like.

#include "sidecar_transport.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

using PyDevices::MPVST::SidecarTransport;
using Clock = std::chrono::steady_clock;

static void report(const char* label, std::vector<double> us)
{
    std::sort(us.begin(), us.end());
    const auto at = [&](double q) { return us[static_cast<std::size_t>(q * double(us.size() - 1))]; };
    std::cout << std::fixed << std::setprecision(1) << label << ": p50 " << at(0.5)
              << " us, p99 " << at(0.99) << " us, max " << us.back() << " us\n";
}

int main(int argc, char** argv)
{
    if (argc < 2)
        return 2;
    const auto frames = argc > 2 ? static_cast<std::uint32_t>(std::atoi(argv[2])) : 128U;
    const auto blocks = argc > 3 ? std::atoi(argv[3]) : 2000;
    setenv("MPVST_ENGINE_PATH", argv[1], 1);
    unsetenv("MPVST_SCRIPT_PATH");
    SidecarTransport transport;
    transport.setScriptSource(
        "import synthio\nimport vstaudio\n"
        "s = synthio.Synthesizer(sample_rate=vstaudio.sample_rate())\n"
        "s.press(synthio.Note(220.0))\nvstaudio.output(s)\n");
    transport.configure(48000.0, frames, 0U);
    if (!transport.start())
        return 4;
    std::vector<float> left(frames), right(frames);
    for (int i = 0; i < 200; ++i)
        transport.process(left.data(), right.data(), frames, false, nullptr, 0U, true);

    for (const bool paced : {false, true})
    {
        std::vector<double> us;
        const auto slot = std::chrono::nanoseconds(
            static_cast<long long>(1e9 * frames / 48000.0));
        auto next = Clock::now();
        for (int i = 0; i < blocks; ++i)
        {
            if (paced)
            {
                next += slot;
                std::this_thread::sleep_until(next);
            }
            const auto t0 = Clock::now();
            transport.process(left.data(), right.data(), frames, false, nullptr, 0U, true);
            us.push_back(std::chrono::duration<double, std::micro>(Clock::now() - t0).count());
        }
        report(paced ? "paced   " : "flat out", us);
    }
    transport.stop();
    return 0;
}
