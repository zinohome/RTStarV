#pragma once

#include <cstdint>
#include <optional>

namespace rtstarv {

struct ImuSample {
    float acc_x, acc_y, acc_z;   // m/s²
    float gyr_x, gyr_y, gyr_z;  // rad/s
    uint32_t timestamp;
    uint8_t  sequence;

    bool has_mag;
    float mag_x, mag_y, mag_z;   // µT (only valid when has_mag)
    uint32_t mag_timestamp;
};

// 解析 64 字节 USB HID 包，返回 IMU 样本（如果是有效 IMU 包）
std::optional<ImuSample> parse_imu_packet(const uint8_t buf[64]);

// 验证包的 CRC 校验和
bool verify_packet_crc(const uint8_t buf[64]);

} // namespace rtstarv
