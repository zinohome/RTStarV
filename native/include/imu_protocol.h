#pragma once

#include <array>
#include <cstdint>
#include <cstring>

namespace rtstarv {

constexpr uint16_t STARV_VID = 0x2A45;
constexpr uint16_t STARV_PID = 0x2050;

constexpr int IFACE_CMD  = 3;
constexpr int IFACE_DATA = 4;

constexpr uint8_t MAGIC = 0x42;
constexpr uint8_t TERMINATOR = 0xFF;
constexpr int PACKET_SIZE = 64;

constexpr uint8_t CAT_IMU = 0x03;
constexpr uint8_t SUB_IMU = 0x02;
constexpr uint8_t MAG_FLAG = 0x33;

constexpr uint8_t ROUTE_IMU_ENABLE = 0x07;
constexpr uint8_t ROUTE_FREQ       = 0x05;
constexpr uint8_t ROUTE_MAG        = 0x10;

enum class FreqCode : uint8_t {
    Hz200  = 0x07,
    Hz100  = 0x08,
    Hz50   = 0x09,
    Hz25   = 0x0A,
    Hz12_5 = 0x0B,
};

// byte[3..end] 的 16-bit 字节求和校验
inline void compute_crc(uint8_t* buf, int payload_start, int payload_len) {
    uint16_t sum = 0;
    for (int i = payload_start; i < payload_start + payload_len; ++i)
        sum += buf[i];
    buf[1] = static_cast<uint8_t>(sum >> 8);
    buf[2] = static_cast<uint8_t>(sum & 0xFF);
}

// 8-byte command: 42 SS CC 06 03 RR VV FF
inline std::array<uint8_t, PACKET_SIZE> build_cmd8(uint8_t route, uint8_t value) {
    std::array<uint8_t, PACKET_SIZE> buf{};
    buf[0] = MAGIC;
    buf[3] = 0x06;
    buf[4] = 0x03;
    buf[5] = route;
    buf[6] = value;
    buf[7] = TERMINATOR;
    compute_crc(buf.data(), 3, 4);
    return buf;
}

// 9-byte command: 42 SS CC 07 03 RR VV XX FF
inline std::array<uint8_t, PACKET_SIZE> build_cmd9(uint8_t route, uint8_t value, uint8_t extra) {
    std::array<uint8_t, PACKET_SIZE> buf{};
    buf[0] = MAGIC;
    buf[3] = 0x07;
    buf[4] = 0x03;
    buf[5] = route;
    buf[6] = value;
    buf[7] = extra;
    buf[8] = TERMINATOR;
    compute_crc(buf.data(), 3, 5);
    return buf;
}

inline auto cmd_imu_enable()  { return build_cmd8(ROUTE_IMU_ENABLE, 0x01); }
inline auto cmd_imu_disable() { return build_cmd8(ROUTE_IMU_ENABLE, 0x00); }
inline auto cmd_set_freq(FreqCode f) { return build_cmd8(ROUTE_FREQ, static_cast<uint8_t>(f)); }
inline auto cmd_mag_enable()  { return build_cmd9(ROUTE_MAG, 0x01, 0x00); }
inline auto cmd_mag_disable() { return build_cmd9(ROUTE_MAG, 0x00, 0x00); }

} // namespace rtstarv
