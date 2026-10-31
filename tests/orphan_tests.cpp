// An engine must not outlive the host that started it.
//
// The parent of this test starts a child that plays the host (it runs a real
// SidecarTransport), kills it the way a crash or a SIGTERM would, with no
// chance to unload anything, and requires the engine it left behind to exit
// on its own. A second child closes normally, to show the engine still exits
// then and the script file the instance wrote is gone.
//
// Linux only: it finds the engine through /proc.

#include "sidecar_transport.h"

#include <chrono>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

#include <sys/wait.h>
#include <unistd.h>

namespace {

using PyDevices::MPVST::SidecarTransport;
namespace fs = std::filesystem;

// The host process: start an instance, report, then either hang about as a
// host does or close the instance the proper way.
int runHost(const char* engine, const std::string& mode)
{
    setenv("MPVST_ENGINE_PATH", engine, 1);
    unsetenv("MPVST_SCRIPT_PATH");
    SidecarTransport transport;
    transport.setScriptSource("import vstaudio\n");
    transport.configure(48000.0, 64U, 256U);
    if (!transport.start())
        return 4;
    if (mode == "clean")
    {
        transport.stop();
        std::cout << "closed" << std::endl;
        return 0;
    }
    std::cout << "ready" << std::endl;
    for (;;)
        std::this_thread::sleep_for(std::chrono::seconds(1));
}

std::vector<pid_t> childrenOf(pid_t parent)
{
    std::vector<pid_t> found;
    for (const auto& entry : fs::directory_iterator("/proc"))
    {
        const auto name = entry.path().filename().string();
        if (name.empty() || name.find_first_not_of("0123456789") != std::string::npos)
            continue;
        std::ifstream stat(entry.path() / "stat");
        std::string line;
        std::getline(stat, line);
        // "pid (comm) S ppid ...": comm may hold spaces, so read from the last ')'.
        const auto close = line.rfind(')');
        if (close == std::string::npos)
            continue;
        pid_t ppid = 0;
        char state = 0;
        if (std::sscanf(line.c_str() + close + 1, " %c %d", &state, &ppid) == 2 &&
            ppid == parent)
            found.push_back(static_cast<pid_t>(std::stol(name)));
    }
    return found;
}

// A process that has exited but not been reaped still has a /proc entry.
bool alive(pid_t pid)
{
    std::ifstream stat("/proc/" + std::to_string(pid) + "/stat");
    std::string line;
    if (!std::getline(stat, line))
        return false;
    const auto close = line.rfind(')');
    return close != std::string::npos && close + 2 < line.size() &&
           line[close + 2] != 'Z';
}

bool waitForExit(pid_t pid, int seconds)
{
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(seconds);
    while (alive(pid))
    {
        if (std::chrono::steady_clock::now() >= deadline)
            return false;
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    return true;
}

struct Host
{
    pid_t pid = -1;
    int fromHost = -1;
};

Host spawnHost(const char* self, const char* engine, const char* mode,
               const fs::path& tmp)
{
    int fds[2];
    if (pipe(fds) != 0)
        return {};
    const auto child = fork();
    if (child == 0)
    {
        dup2(fds[1], STDOUT_FILENO);
        close(fds[0]);
        close(fds[1]);
        setenv("TMPDIR", tmp.c_str(), 1);
        execl(self, self, "--host", engine, mode, static_cast<char*>(nullptr));
        _exit(127);
    }
    close(fds[1]);
    return {child, fds[0]};
}

std::string readLine(int fd)
{
    std::string line;
    char c = 0;
    while (read(fd, &c, 1) == 1 && c != '\n')
        line.push_back(c);
    return line;
}

std::size_t countFiles(const fs::path& dir)
{
    std::size_t count = 0;
    for (const auto& entry : fs::directory_iterator(dir))
    {
        (void)entry;
        ++count;
    }
    return count;
}

} // namespace

int main(int argc, char** argv)
{
    if (argc == 4 && std::string(argv[1]) == "--host")
        return runHost(argv[2], argv[3]);
    if (argc != 2)
        return 2;

    const auto tmp = fs::temp_directory_path() /
        ("mpvst-orphan-test-" + std::to_string(getpid()));
    fs::create_directories(tmp);
    int result = 0;

    // The host dies without closing anything.
    {
        auto host = spawnHost(argv[0], argv[1], "crash", tmp);
        if (readLine(host.fromHost) != "ready")
        {
            std::cerr << "the host never started an engine\n";
            result = 3;
        }
        else
        {
            const auto engines = childrenOf(host.pid);
            if (engines.size() != 1U)
            {
                std::cerr << "expected one engine under the host, found "
                          << engines.size() << '\n';
                result = 4;
            }
            else
            {
                kill(host.pid, SIGKILL);
                int status = 0;
                waitpid(host.pid, &status, 0);
                if (!waitForExit(engines[0], 5))
                {
                    std::cerr << "FAIL: the engine is still running 5 s after its host died\n";
                    kill(engines[0], SIGKILL);
                    result = 5;
                }
                else
                {
                    std::cout << "the engine exited after its host was killed\n";
                }
            }
        }
        close(host.fromHost);
    }

    // The host closes the instance properly.
    {
        auto host = spawnHost(argv[0], argv[1], "clean", tmp);
        const auto line = readLine(host.fromHost);
        int status = 0;
        waitpid(host.pid, &status, 0);
        close(host.fromHost);
        if (line != "closed")
        {
            std::cerr << "the host could not start and close an instance\n";
            result = result != 0 ? result : 6;
        }
        else
        {
            std::cout << "a normal close still works\n";
        }
    }

    // A killed host cannot clean up its own script file; a clean close must.
    const auto leftovers = countFiles(tmp);
    if (leftovers > 1U)
    {
        std::cerr << "FAIL: a clean close left " << (leftovers - 1U)
                  << " script file(s) behind\n";
        result = result != 0 ? result : 7;
    }
    std::error_code ignored;
    fs::remove_all(tmp, ignored);
    return result;
}
