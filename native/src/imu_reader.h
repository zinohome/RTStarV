#pragma once

#include "imu_parser.h"
#include "usb_device.h"
#include <atomic>
#include <thread>

namespace rtstarv {

class ImuReader {
public:
    explicit ImuReader(UsbDevice& device);
    ~ImuReader();

    ImuReader(const ImuReader&) = delete;
    ImuReader& operator=(const ImuReader&) = delete;

    // 启用 IMU 流，启动后台读取线程
    bool start(FreqCode freq = FreqCode::Hz200, bool enable_mag = false);

    // 停止读取，禁用 IMU
    void stop();

    bool is_running() const;

    // 获取最新样本（lock-free 读取），返回是否有新数据
    bool get_latest(ImuSample& out) const;

    // 丢帧统计
    uint32_t dropped_frames() const;

private:
    void reader_loop();

    UsbDevice& device_;
    std::atomic<bool> running_{false};
    std::thread thread_;
    bool mag_enabled_ = false;

    // 双缓冲: 写线程写 write_idx，读线程读另一个
    mutable std::atomic<int> write_idx_{0};
    ImuSample samples_[2]{};
    std::atomic<uint32_t> sample_count_{0};
    std::atomic<uint32_t> dropped_{0};
    uint8_t last_seq_ = 0;
    bool first_packet_ = true;
};

} // namespace rtstarv
