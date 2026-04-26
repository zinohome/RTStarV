#include "usb_device.h"
#include <hidapi.h>
#include <cstring>

namespace rtstarv {

// -- HidHandle --

void UsbDevice::HidHandle::close() {
    if (ptr) {
        hid_close(ptr);
        ptr = nullptr;
    }
}

UsbDevice::HidHandle::~HidHandle() { close(); }

// -- UsbDevice --

UsbDevice::UsbDevice() = default;

UsbDevice::~UsbDevice() { close(); }

static hid_device* open_by_interface(int target_iface) {
    struct hid_device_info* devs = hid_enumerate(STARV_VID, STARV_PID);
    if (!devs) return nullptr;

    hid_device* result = nullptr;
    for (auto* d = devs; d; d = d->next) {
        if (d->interface_number == target_iface) {
            result = hid_open_path(d->path);
            break;
        }
    }
    hid_free_enumeration(devs);
    return result;
}

bool UsbDevice::open() {
    if (opened_) return true;

    if (hid_init() != 0) return false;

    cmd_handle_.ptr = open_by_interface(IFACE_CMD);
    if (!cmd_handle_.ptr) {
        hid_exit();
        return false;
    }

    data_handle_.ptr = open_by_interface(IFACE_DATA);
    if (!data_handle_.ptr) {
        cmd_handle_.close();
        hid_exit();
        return false;
    }

    hid_set_nonblocking(data_handle_.ptr, 1);
    opened_ = true;
    return true;
}

void UsbDevice::close() {
    if (!opened_) return;
    data_handle_.close();
    cmd_handle_.close();
    hid_exit();
    opened_ = false;
}

bool UsbDevice::is_open() const { return opened_; }

bool UsbDevice::send_command(const std::array<uint8_t, PACKET_SIZE>& cmd) {
    if (!opened_) return false;
    // Windows HID 需要在前面加 Report ID 0x00
    uint8_t buf[PACKET_SIZE + 1];
    buf[0] = 0x00;
    std::memcpy(buf + 1, cmd.data(), PACKET_SIZE);
    return hid_write(cmd_handle_.ptr, buf, sizeof(buf)) >= 0;
}

int UsbDevice::read_packet(uint8_t buf[PACKET_SIZE]) {
    if (!opened_) return -1;
    return hid_read(data_handle_.ptr, buf, PACKET_SIZE);
}

void UsbDevice::set_nonblocking(bool enabled) {
    if (data_handle_.ptr)
        hid_set_nonblocking(data_handle_.ptr, enabled ? 1 : 0);
}

std::string UsbDevice::product_string() const {
    if (!cmd_handle_.ptr) return "";
    wchar_t wbuf[128]{};
    if (hid_get_product_string(cmd_handle_.ptr, wbuf, 128) != 0)
        return "";
    std::string result;
    for (int i = 0; wbuf[i]; ++i)
        result += static_cast<char>(wbuf[i]);
    return result;
}

} // namespace rtstarv
