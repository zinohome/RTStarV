// platform/windows/idd_driver/driver/Driver.cpp
#include "Driver.h"

extern "C" NTSTATUS DriverEntry(PDRIVER_OBJECT DriverObject, PUNICODE_STRING RegistryPath) {
    WDF_DRIVER_CONFIG config;
    WDF_DRIVER_CONFIG_INIT(&config, EvtDeviceAdd);
    return WdfDriverCreate(DriverObject, RegistryPath, WDF_NO_OBJECT_ATTRIBUTES, &config, WDF_NO_HANDLE);
}

NTSTATUS EvtDeviceAdd(WDFDRIVER Driver, PWDFDEVICE_INIT DeviceInit) {
    UNREFERENCED_PARAMETER(Driver);

    IDD_CX_CLIENT_CONFIG iddConfig = {};
    iddConfig.Size = sizeof(iddConfig);
    iddConfig.EvtIddCxAdapterInitFinished = EvtAdapterInitFinished;
    iddConfig.EvtIddCxAdapterCommitModes = EvtAdapterCommitModes;
    iddConfig.EvtIddCxMonitorGetDefaultDescriptionModes = EvtMonitorGetDefaultModes;
    iddConfig.EvtIddCxMonitorAssignSwapChain = EvtMonitorAssignSwapChain;
    iddConfig.EvtIddCxMonitorUnassignSwapChain = EvtMonitorUnassignSwapChain;

    NTSTATUS status = IddCxDeviceInitConfig(DeviceInit, &iddConfig);
    if (!NT_SUCCESS(status)) return status;

    WDF_OBJECT_ATTRIBUTES attr;
    WDF_OBJECT_ATTRIBUTES_INIT_CONTEXT_TYPE(&attr, DeviceContext);

    WDFDEVICE device;
    status = WdfDeviceCreate(&DeviceInit, &attr, &device);
    if (!NT_SUCCESS(status)) return status;

    auto* ctx = GetDeviceContext(device);
    ctx->wdf_device = device;
    ctx->monitor_count = 0;

    status = WdfDeviceCreateDeviceInterface(device, &GUID_RTSTARV_DISPLAY, nullptr);
    if (!NT_SUCCESS(status)) return status;

    WDF_IO_QUEUE_CONFIG queueConfig;
    WDF_IO_QUEUE_CONFIG_INIT_DEFAULT_QUEUE(&queueConfig, WdfIoQueueDispatchSequential);
    queueConfig.EvtIoDeviceControl = EvtIoDeviceControl;
    WdfIoQueueCreate(device, &queueConfig, WDF_NO_OBJECT_ATTRIBUTES, nullptr);

    IDDCX_ADAPTER_CAPS caps = {};
    caps.Size = sizeof(caps);
    caps.MaxMonitorsSupported = 6;

    IDARG_IN_ADAPTER_INIT adapterInit = {};
    adapterInit.WdfDevice = device;
    adapterInit.pCaps = &caps;

    IDARG_OUT_ADAPTER_INIT adapterOut = {};
    status = IddCxAdapterInitAsync(&adapterInit, &adapterOut);

    if (NT_SUCCESS(status))
        ctx->adapter_handle = adapterOut.AdapterObject;

    return status;
}

NTSTATUS EvtAdapterInitFinished(IDDCX_ADAPTER Adapter, const IDARG_IN_ADAPTER_INIT_FINISHED* pInArgs) {
    UNREFERENCED_PARAMETER(Adapter);
    return pInArgs->AdapterInitStatus;
}

NTSTATUS EvtAdapterCommitModes(IDDCX_ADAPTER Adapter, const IDARG_IN_COMMITMODES* pInArgs) {
    UNREFERENCED_PARAMETER(Adapter);
    UNREFERENCED_PARAMETER(pInArgs);
    return STATUS_SUCCESS;
}
