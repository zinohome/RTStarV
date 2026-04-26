#include "../src/imu_parser.h"
#include "../include/imu_protocol.h"
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

using namespace rtstarv;

static std::array<uint8_t, 64> hex_to_bytes(const char* hex) {
    std::array<uint8_t, 64> buf{};
    int idx = 0;
    const char* p = hex;
    while (*p && idx < 64) {
        while (*p == ' ') ++p;
        if (!*p) break;
        unsigned val;
        sscanf(p, "%02x", &val);
        buf[idx++] = static_cast<uint8_t>(val);
        p += 2;
    }
    return buf;
}

static bool near(float a, float b, float tol = 0.01f) {
    return std::fabs(a - b) < tol;
}

// ===== 命令构建测试 =====

static void test_cmd_imu_enable() {
    auto cmd = cmd_imu_enable();
    assert(cmd[0] == 0x42);
    assert(cmd[1] == 0x00 && cmd[2] == 0x11); // CRC of 06+03+07+01 = 0x0011
    assert(cmd[3] == 0x06);
    assert(cmd[4] == 0x03);
    assert(cmd[5] == 0x07);
    assert(cmd[6] == 0x01);
    assert(cmd[7] == 0xFF);
    printf("  PASS: cmd_imu_enable\n");
}

static void test_cmd_imu_disable() {
    auto cmd = cmd_imu_disable();
    assert(cmd[0] == 0x42);
    assert(cmd[1] == 0x00 && cmd[2] == 0x10);
    assert(cmd[6] == 0x00);
    assert(cmd[7] == 0xFF);
    printf("  PASS: cmd_imu_disable\n");
}

static void test_cmd_set_freq_200hz() {
    auto cmd = cmd_set_freq(FreqCode::Hz200);
    // 42 00 15 06 03 05 07 ff (validated on device)
    assert(cmd[0] == 0x42);
    assert(cmd[1] == 0x00 && cmd[2] == 0x15);
    assert(cmd[5] == 0x05);
    assert(cmd[6] == 0x07);
    assert(cmd[7] == 0xFF);
    printf("  PASS: cmd_set_freq(200Hz)\n");
}

static void test_cmd_mag_enable() {
    auto cmd = cmd_mag_enable();
    // 42 00 1b 07 03 10 01 00 ff (validated on device)
    assert(cmd[0] == 0x42);
    assert(cmd[1] == 0x00 && cmd[2] == 0x1b);
    assert(cmd[3] == 0x07);
    assert(cmd[5] == 0x10);
    assert(cmd[6] == 0x01);
    assert(cmd[7] == 0x00);
    assert(cmd[8] == 0xFF);
    printf("  PASS: cmd_mag_enable\n");
}

// ===== 包解析测试 =====

// 从 imu_v2_20260426_205619.json 捕获的真实 IMU 包
static void test_parse_imu_basic() {
    auto buf = hex_to_bytes(
        "42 0b 8c 27 03 02 84 03 "
        "c8 ce f4 3d 1c c4 dd bf "
        "3c f7 19 41 3b 0c 79 3d "
        "17 f0 06 3d a0 c4 9d bc "
        "2f 8c 02 00 a1 01 00 00 "
        "ff 00 00 00 00 00 00 00 "
        "00 00 00 00 00 00 00 00 "
        "00 00 00 00 00 00 00 00");

    auto s = parse_imu_packet(buf.data());
    assert(s.has_value());

    float acc_mag = std::sqrt(s->acc_x*s->acc_x + s->acc_y*s->acc_y + s->acc_z*s->acc_z);
    assert(acc_mag > 9.0f && acc_mag < 10.5f); // ~g

    assert(s->sequence == 0x84);
    assert(!s->has_mag);
    assert(s->timestamp > 0);

    printf("  PASS: parse_imu_basic (|acc|=%.2f)\n", acc_mag);
}

// 从 mag_full_20260426_212415.json 捕获的普通 IMU 包（磁力计已启用但此包无 mag 数据）
static void test_parse_imu_no_mag() {
    auto buf = hex_to_bytes(
        "42 0c 8d 27 03 02 88 03 "
        "0a 35 eb bc b7 5b db c0 "
        "0f 02 d4 40 51 e7 82 3c "
        "7e 5b 14 3d 7f 89 46 3d "
        "bd 54 0a 00 13 03 00 00 "
        "ff 00 00 00 00 00 00 00 "
        "00 00 00 00 00 00 00 00 "
        "00 00 00 00 00 00 00 00");

    auto s = parse_imu_packet(buf.data());
    assert(s.has_value());
    assert(!s->has_mag);
    assert(s->sequence == 0x88);

    float acc_mag = std::sqrt(s->acc_x*s->acc_x + s->acc_y*s->acc_y + s->acc_z*s->acc_z);
    assert(acc_mag > 9.0f && acc_mag < 10.5f);

    printf("  PASS: parse_imu_no_mag (|acc|=%.2f)\n", acc_mag);
}

// 从 mag_full_20260426_212415.json 捕获的扩展包（含磁力计数据）
static void test_parse_imu_with_mag() {
    auto buf = hex_to_bytes(
        "42 11 f6 3b 03 02 8b 33 "
        "07 ce 9c bb 1b 22 da c0 "
        "73 2a d3 40 1b 72 51 bb "
        "5d 44 07 3d e3 a0 3b 3d "
        "1b 8f 0a 00 13 03 00 00 "
        "00 e4 3b 42 00 6c 9d 42 "
        "00 00 fa c1 b3 86 0a 00 "
        "13 03 00 00 ff 00 00 00");

    auto s = parse_imu_packet(buf.data());
    assert(s.has_value());
    assert(s->has_mag);
    assert(s->sequence == 0x8b);

    // Python 解码验证值: mag = (46.973, 78.711, -31.250)
    assert(near(s->mag_x, 46.973f, 0.01f));
    assert(near(s->mag_y, 78.711f, 0.01f));
    assert(near(s->mag_z, -31.250f, 0.01f));

    float mag_mag = std::sqrt(s->mag_x*s->mag_x + s->mag_y*s->mag_y + s->mag_z*s->mag_z);
    assert(mag_mag > 90.0f && mag_mag < 110.0f); // ~97 µT

    assert(s->mag_timestamp == 689843);
    assert(s->timestamp == 691995);

    printf("  PASS: parse_imu_with_mag (mag=(%.1f, %.1f, %.1f) |mag|=%.1f)\n",
           s->mag_x, s->mag_y, s->mag_z, mag_mag);
}

// 第二个扩展包，交叉验证
static void test_parse_imu_with_mag_2() {
    auto buf = hex_to_bytes(
        "42 15 e1 3b 03 02 8f 33 "
        "0a 35 eb 3c b6 f9 da c0 "
        "7c 60 d7 40 d8 43 b7 bc "
        "7f b7 f8 3c 25 a1 23 3d "
        "ee dc 0a 00 13 03 00 00 "
        "00 e4 3b 42 00 3a 9d 42 "
        "00 00 fa c1 ca d4 0a 00 "
        "13 03 00 00 ff 00 00 00");

    auto s = parse_imu_packet(buf.data());
    assert(s.has_value());
    assert(s->has_mag);

    // mag_x should be very close to first sample (static field)
    assert(near(s->mag_x, 46.973f, 0.1f));
    assert(near(s->mag_z, -31.250f, 0.1f));

    printf("  PASS: parse_imu_with_mag_2 (mag_x=%.1f)\n", s->mag_x);
}

// 非 IMU 包（错误的 magic 或 category）应返回 nullopt
static void test_reject_invalid() {
    std::array<uint8_t, 64> buf{};
    assert(!parse_imu_packet(buf.data()).has_value()); // magic=0

    buf[0] = 0x42;
    buf[4] = 0x01; // wrong category
    buf[5] = 0x07;
    assert(!parse_imu_packet(buf.data()).has_value());

    printf("  PASS: reject_invalid\n");
}

// ===== CRC 校验测试 =====

static void test_crc_computation() {
    // 42 00 11 06 03 07 01 FF → CRC of [06,03,07,01] = 0x0011
    std::array<uint8_t, PACKET_SIZE> buf{};
    buf[0] = 0x42;
    buf[3] = 0x06; buf[4] = 0x03; buf[5] = 0x07; buf[6] = 0x01;
    compute_crc(buf.data(), 3, 4);
    assert(buf[1] == 0x00 && buf[2] == 0x11);

    // 42 00 15 06 03 05 07 FF → CRC = 0x0015
    buf = {};
    buf[0] = 0x42;
    buf[3] = 0x06; buf[4] = 0x03; buf[5] = 0x05; buf[6] = 0x07;
    compute_crc(buf.data(), 3, 4);
    assert(buf[1] == 0x00 && buf[2] == 0x15);

    // 42 00 1b 07 03 10 01 00 FF → CRC of [07,03,10,01,00] = 0x001b
    buf = {};
    buf[0] = 0x42;
    buf[3] = 0x07; buf[4] = 0x03; buf[5] = 0x10; buf[6] = 0x01; buf[7] = 0x00;
    compute_crc(buf.data(), 3, 5);
    assert(buf[1] == 0x00 && buf[2] == 0x1b);

    printf("  PASS: crc_computation\n");
}

// ===== 全频率命令测试 =====

static void test_all_freq_commands() {
    struct { FreqCode code; uint8_t hi; uint8_t lo; } cases[] = {
        {FreqCode::Hz200,  0x00, 0x15},
        {FreqCode::Hz100,  0x00, 0x16},
        {FreqCode::Hz50,   0x00, 0x17},
        {FreqCode::Hz25,   0x00, 0x18},
        {FreqCode::Hz12_5, 0x00, 0x19},
    };
    for (auto& c : cases) {
        auto cmd = cmd_set_freq(c.code);
        assert(cmd[1] == c.hi && cmd[2] == c.lo);
    }
    printf("  PASS: all_freq_commands (5 rates)\n");
}

int main() {
    printf("=== RTStarV IMU Parser Tests ===\n\n");

    printf("[Command Builder]\n");
    test_cmd_imu_enable();
    test_cmd_imu_disable();
    test_cmd_set_freq_200hz();
    test_cmd_mag_enable();
    test_all_freq_commands();

    printf("\n[CRC]\n");
    test_crc_computation();

    printf("\n[Packet Parser]\n");
    test_parse_imu_basic();
    test_parse_imu_no_mag();
    test_parse_imu_with_mag();
    test_parse_imu_with_mag_2();
    test_reject_invalid();

    printf("\n=== ALL %d TESTS PASSED ===\n", 11);
    return 0;
}
