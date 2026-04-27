// platform/windows/src/virtual_display.cpp
#include "virtual_display.h"
#include <cstdlib>
#include <setupapi.h>
#include <initguid.h>

DEFINE_GUID(GUID_RTSTARV_DISPLAY,
    0xf5a6c93e, 0x2dd6, 0x4b9a, 0x8f, 0xa3, 0x7a, 0x2d, 0x50, 0xb2, 0x5c, 0x21);

#define IOCTL_RTSTARV_ADD_MONITOR    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_RTSTARV_REMOVE_MONITOR CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)

bool VirtualDisplay::init() {
    HDEVINFO devInfo = SetupDiGetClassDevs(&GUID_RTSTARV_DISPLAY, nullptr, nullptr,
                                            DIGCF_PRESENT | DIGCF_DEVICEINTERFACE);
    if (devInfo == INVALID_HANDLE_VALUE) return false;

    SP_DEVICE_INTERFACE_DATA ifData = {};
    ifData.cbSize = sizeof(ifData);

    if (!SetupDiEnumDeviceInterfaces(devInfo, nullptr, &GUID_RTSTARV_DISPLAY, 0, &ifData)) {
        SetupDiDestroyDeviceInfoList(devInfo);
        return false;
    }

    DWORD size = 0;
    SetupDiGetDeviceInterfaceDetailW(devInfo, &ifData, nullptr, 0, &size, nullptr);

    auto* detail = (SP_DEVICE_INTERFACE_DETAIL_DATA_W*)malloc(size);
    if (!detail) { SetupDiDestroyDeviceInfoList(devInfo); return false; }
    detail->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W);
    SetupDiGetDeviceInterfaceDetailW(devInfo, &ifData, detail, size, nullptr, nullptr);

    handle_ = CreateFileW(detail->DevicePath, GENERIC_READ | GENERIC_WRITE,
                          0, nullptr, OPEN_EXISTING, 0, nullptr);

    free(detail);
    SetupDiDestroyDeviceInfoList(devInfo);
    return handle_ != INVALID_HANDLE_VALUE;
}

void VirtualDisplay::destroy() {
    while (count_ > 0) remove_monitor();
    if (handle_ != INVALID_HANDLE_VALUE) {
        CloseHandle(handle_);
        handle_ = INVALID_HANDLE_VALUE;
    }
}

bool VirtualDisplay::add_monitor(int width, int height) {
    if (handle_ == INVALID_HANDLE_VALUE) return false;
    UINT dims[2] = {(UINT)width, (UINT)height};
    DWORD returned;
    BOOL ok = DeviceIoControl(handle_, IOCTL_RTSTARV_ADD_MONITOR,
                              dims, sizeof(dims), nullptr, 0, &returned, nullptr);
    if (ok) count_++;
    return ok != FALSE;
}

bool VirtualDisplay::remove_monitor() {
    if (handle_ == INVALID_HANDLE_VALUE || count_ <= 0) return false;
    DWORD returned;
    BOOL ok = DeviceIoControl(handle_, IOCTL_RTSTARV_REMOVE_MONITOR,
                              nullptr, 0, nullptr, 0, &returned, nullptr);
    if (ok) count_--;
    return ok != FALSE;
}
