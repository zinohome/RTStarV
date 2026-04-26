// platform/windows/idd_driver/driver/Device.cpp
#include "Driver.h"

static NTSTATUS AddMonitor(DeviceContext* ctx, UINT width, UINT height) {
    if (ctx->monitor_count >= 6) return STATUS_INSUFFICIENT_RESOURCES;

    int idx = ctx->monitor_count;
    auto& mon = ctx->monitors[idx];
    mon.width = width;
    mon.height = height;
    mon.running = true;

    IDDCX_MONITOR_INFO info = {};
    info.Size = sizeof(info);
    info.MonitorType = DISPLAYCONFIG_OUTPUT_TECHNOLOGY_OTHER;
    info.ConnectorIndex = idx;

    static const BYTE edid_1080p[] = {
        0x00,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0x00, 0x4A,0x8B,0x01,0x00,0x01,0x00,0x00,0x00,
        0x01,0x1E,0x01,0x04,0xA5,0x35,0x1E,0x78, 0x02,0x68,0xF5,0xA6,0x55,0x50,0xA0,0x23,
        0x0B,0x50,0x54,0x00,0x00,0x00,0x01,0x01, 0x01,0x01,0x01,0x01,0x01,0x01,0x01,0x01,
        0x01,0x01,0x01,0x01,0x01,0x01,0x02,0x3A, 0x80,0x18,0x71,0x38,0x2D,0x40,0x58,0x2C,
        0x45,0x00,0x0F,0x48,0x42,0x00,0x00,0x1E, 0x00,0x00,0x00,0xFC,0x00,0x52,0x54,0x53,
        0x74,0x61,0x72,0x56,0x0A,0x20,0x20,0x20, 0x20,0x20,0x00,0x00,0x00,0xFD,0x00,0x30,
        0x78,0x1E,0x8C,0x1E,0x00,0x0A,0x20,0x20, 0x20,0x20,0x20,0x20,0x00,0x00,0x00,0x10,
        0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00, 0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x2D
    };

    info.MonitorDescription.Size = sizeof(info.MonitorDescription);
    info.MonitorDescription.Type = IDDCX_MONITOR_DESCRIPTION_TYPE_EDID;
    info.MonitorDescription.DataSize = sizeof(edid_1080p);
    info.MonitorDescription.pData = (void*)edid_1080p;

    IDARG_IN_MONITORCREATE create = {};
    create.ObjectAttributes = WDF_NO_OBJECT_ATTRIBUTES;
    create.pMonitorInfo = &info;

    IDARG_OUT_MONITORCREATE createOut = {};
    NTSTATUS status = IddCxMonitorCreate(ctx->adapter_handle, &create, &createOut);
    if (!NT_SUCCESS(status)) return status;

    mon.monitor_handle = createOut.MonitorObject;

    IDARG_OUT_MONITORARRIVAL arrivalOut = {};
    status = IddCxMonitorArrival(mon.monitor_handle, &arrivalOut);
    if (NT_SUCCESS(status))
        ctx->monitor_count++;

    return status;
}

static NTSTATUS RemoveMonitor(DeviceContext* ctx) {
    if (ctx->monitor_count <= 0) return STATUS_INVALID_PARAMETER;

    int idx = ctx->monitor_count - 1;
    auto& mon = ctx->monitors[idx];
    mon.running = false;

    IddCxMonitorDeparture(mon.monitor_handle);
    ctx->monitor_count--;
    return STATUS_SUCCESS;
}

VOID EvtIoDeviceControl(WDFQUEUE Queue, WDFREQUEST Request, size_t OutputBufferLength,
                        size_t InputBufferLength, ULONG IoControlCode) {
    UNREFERENCED_PARAMETER(OutputBufferLength);

    auto device = WdfIoQueueGetDevice(Queue);
    auto* ctx = GetDeviceContext(device);
    NTSTATUS status = STATUS_INVALID_PARAMETER;

    switch (IoControlCode) {
    case IOCTL_RTSTARV_ADD_MONITOR: {
        if (InputBufferLength >= 8) {
            PVOID buf;
            WdfRequestRetrieveInputBuffer(Request, 8, &buf, nullptr);
            UINT* dims = (UINT*)buf;
            status = AddMonitor(ctx, dims[0], dims[1]);
        }
        break;
    }
    case IOCTL_RTSTARV_REMOVE_MONITOR:
        status = RemoveMonitor(ctx);
        break;
    }

    WdfRequestComplete(Request, status);
}
