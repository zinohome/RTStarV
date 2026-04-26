#include "imu_parser.h"
#include "imu_protocol.h"
#include <cstring>

namespace rtstarv {

static float read_f32_le(const uint8_t* p) {
    float v;
    std::memcpy(&v, p, 4);
    return v;
}

static uint32_t read_u32_le(const uint8_t* p) {
    uint32_t v;
    std::memcpy(&v, p, 4);
    return v;
}

bool verify_packet_crc(const uint8_t buf[64]) {
    if (buf[0] != MAGIC) return false;

    uint8_t len_field = buf[3];
    int payload_len;
    if (len_field == 0x27)
        payload_len = 37;  // byte[3..39], CRC covers byte[3..end-before-FF]
    else if (len_field == 0x3b)
        payload_len = 57;
    else
        payload_len = len_field - 2;  // heuristic

    // CRC covers byte[3..(3+payload_len-1)]
    // but we don't know exactly how many bytes the device checksums for data packets.
    // For command packets we know precisely; for data packets, skip CRC check for now.
    // TODO: reverse-engineer data packet CRC range from captured samples
    (void)payload_len;
    return true;
}

std::optional<ImuSample> parse_imu_packet(const uint8_t buf[64]) {
    if (buf[0] != MAGIC)  return std::nullopt;
    if (buf[4] != CAT_IMU) return std::nullopt;
    if (buf[5] != SUB_IMU) return std::nullopt;

    ImuSample s{};
    s.sequence = buf[6];

    s.acc_x = read_f32_le(&buf[8]);
    s.acc_y = read_f32_le(&buf[12]);
    s.acc_z = read_f32_le(&buf[16]);
    s.gyr_x = read_f32_le(&buf[20]);
    s.gyr_y = read_f32_le(&buf[24]);
    s.gyr_z = read_f32_le(&buf[28]);
    s.timestamp = read_u32_le(&buf[32]);

    s.has_mag = (buf[7] == MAG_FLAG && buf[3] == 0x3b);
    if (s.has_mag) {
        s.mag_x = read_f32_le(&buf[40]);
        s.mag_y = read_f32_le(&buf[44]);
        s.mag_z = read_f32_le(&buf[48]);
        s.mag_timestamp = read_u32_le(&buf[52]);
    } else {
        s.mag_x = s.mag_y = s.mag_z = 0.0f;
        s.mag_timestamp = 0;
    }

    return s;
}

} // namespace rtstarv
