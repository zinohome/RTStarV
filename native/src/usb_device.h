#pragma once

#include "imu_protocol.h"
#include <cstdint>
#include <functional>
#include <memory>
#include <string>

struct hid_device_;  // forward decl from hidapi

namespace rtstarv {

class UsbDevice {
public:
    UsbDevice();
    ~UsbDevice();

    UsbDevice(const UsbDevice&) = delete;
    UsbDevice& operator=(const UsbDevice&) = delete;

    bool open();
    void close();
    bool is_open() const;

    // 发送 64 字节命令到 interface 3 (自动添加 Report ID 0x00)
    bool send_command(const std::array<uint8_t, PACKET_SIZE>& cmd);

    // 从 interface 4 非阻塞读取一个包，返回读取字节数 (0=无数据)
    int read_packet(uint8_t buf[PACKET_SIZE]);

    // 设置非阻塞模式
    void set_nonblocking(bool enabled);

    std::string product_string() const;

private:
    struct HidHandle {
        hid_device_* ptr = nullptr;
        void close();
        ~HidHandle();
    };

    HidHandle cmd_handle_;
    HidHandle data_handle_;
    bool opened_ = false;
};

} // namespace rtstarv
