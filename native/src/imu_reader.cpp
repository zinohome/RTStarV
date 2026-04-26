#include "imu_reader.h"
#include <chrono>

namespace rtstarv {

ImuReader::ImuReader(UsbDevice& device) : device_(device) {}

ImuReader::~ImuReader() { stop(); }

bool ImuReader::start(FreqCode freq, bool enable_mag) {
    if (running_) return true;
    if (!device_.is_open()) return false;

    if (!device_.send_command(cmd_set_freq(freq))) return false;
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    if (!device_.send_command(cmd_imu_enable())) return false;
    std::this_thread::sleep_for(std::chrono::milliseconds(300));

    mag_enabled_ = enable_mag;
    if (mag_enabled_) {
        if (!device_.send_command(cmd_mag_enable())) return false;
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
    }

    // 清空积压的包
    uint8_t drain[PACKET_SIZE];
    for (int i = 0; i < 500; ++i)
        if (device_.read_packet(drain) <= 0) break;

    first_packet_ = true;
    dropped_ = 0;
    sample_count_ = 0;
    running_ = true;
    thread_ = std::thread(&ImuReader::reader_loop, this);
    return true;
}

void ImuReader::stop() {
    if (!running_) return;
    running_ = false;
    if (thread_.joinable()) thread_.join();

    if (mag_enabled_)
        device_.send_command(cmd_mag_disable());
    device_.send_command(cmd_imu_disable());
    mag_enabled_ = false;
}

bool ImuReader::is_running() const { return running_; }

bool ImuReader::get_latest(ImuSample& out) const {
    if (sample_count_ == 0) return false;
    int idx = write_idx_.load(std::memory_order_acquire);
    int read_idx = 1 - idx;  // 读取写线程未在写的那个
    out = samples_[read_idx];
    return true;
}

uint32_t ImuReader::dropped_frames() const {
    return dropped_.load(std::memory_order_relaxed);
}

void ImuReader::reader_loop() {
    uint8_t buf[PACKET_SIZE];
    while (running_) {
        int n = device_.read_packet(buf);
        if (n <= 0) {
            std::this_thread::sleep_for(std::chrono::microseconds(500));
            continue;
        }

        auto sample = parse_imu_packet(buf);
        if (!sample) continue;

        // 丢帧检测
        if (!first_packet_) {
            uint8_t expected = last_seq_ + 1;
            if (sample->sequence != expected) {
                uint8_t gap = sample->sequence - expected;
                dropped_ += gap;
            }
        }
        last_seq_ = sample->sequence;
        first_packet_ = false;

        // 双缓冲写入
        int next = 1 - write_idx_.load(std::memory_order_relaxed);
        samples_[next] = *sample;
        write_idx_.store(next, std::memory_order_release);
        sample_count_.fetch_add(1, std::memory_order_relaxed);
    }
}

} // namespace rtstarv
