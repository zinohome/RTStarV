// platform/windows/idd_driver/driver/Driver.h
#pragma once

#include <windows.h>
#include <wdf.h>
#include <IddCx.h>
#include <wrl.h>

// {F5A6C93E-2DD6-4B9A-8FA3-7A2D50B25C21}
DEFINE_GUID(GUID_RTSTARV_DISPLAY,
    0xf5a6c93e, 0x2dd6, 0x4b9a, 0x8f, 0xa3, 0x7a, 0x2d, 0x50, 0xb2, 0x5c, 0x21);

#define IOCTL_RTSTARV_ADD_MONITOR    CTL_CODE(FILE_DEVICE_UNKNOWN, 0x801, METHOD_BUFFERED, FILE_ANY_ACCESS)
#define IOCTL_RTSTARV_REMOVE_MONITOR CTL_CODE(FILE_DEVICE_UNKNOWN, 0x802, METHOD_BUFFERED, FILE_ANY_ACCESS)

struct DeviceContext; // forward decl

struct MonitorContext {
    IDDCX_MONITOR monitor_handle;
    IDDCX_SWAPCHAIN swapchain_handle;
    HANDLE thread_handle;
    bool running;
    UINT width;
    UINT height;
    DeviceContext* parent;
};

struct DeviceContext {
    WDFDEVICE wdf_device;
    IDDCX_ADAPTER adapter_handle;
    MonitorContext monitors[6];
    int monitor_count;
};

WDF_DECLARE_CONTEXT_TYPE_WITH_NAME(DeviceContext, GetDeviceContext);

extern "C" DRIVER_INITIALIZE DriverEntry;
EVT_WDF_DRIVER_DEVICE_ADD EvtDeviceAdd;
EVT_IDD_CX_ADAPTER_INIT_FINISHED EvtAdapterInitFinished;
EVT_IDD_CX_ADAPTER_COMMIT_MODES EvtAdapterCommitModes;
EVT_IDD_CX_MONITOR_GET_DEFAULT_DESCRIPTION_MODES EvtMonitorGetDefaultModes;
EVT_IDD_CX_MONITOR_ASSIGN_SWAPCHAIN EvtMonitorAssignSwapChain;
EVT_IDD_CX_MONITOR_UNASSIGN_SWAPCHAIN EvtMonitorUnassignSwapChain;
VOID EvtIoDeviceControl(WDFQUEUE, WDFREQUEST, size_t, size_t, ULONG);
