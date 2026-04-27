// platform/windows/idd_driver/driver/SwapChain.cpp
#include "Driver.h"

NTSTATUS EvtMonitorGetDefaultModes(IDDCX_MONITOR Monitor,
    const IDARG_IN_GETDEFAULTDESCRIPTIONMODES* pIn,
    IDARG_OUT_GETDEFAULTDESCRIPTIONMODES* pOut) {
    UNREFERENCED_PARAMETER(Monitor);

    if (pIn->DefaultMonitorModeBufferOutputCount == 0) {
        pOut->DefaultMonitorModeBufferOutputCount = 1;
        return STATUS_BUFFER_TOO_SMALL;
    }

    IDDCX_MONITOR_MODE mode = {};
    mode.Size = sizeof(mode);
    mode.Origin = IDDCX_MONITOR_MODE_ORIGIN_DRIVER;
    mode.MonitorVideoSignalInfo.totalSize.cx = 1920;
    mode.MonitorVideoSignalInfo.totalSize.cy = 1080;
    mode.MonitorVideoSignalInfo.activeSize = mode.MonitorVideoSignalInfo.totalSize;
    mode.MonitorVideoSignalInfo.vSyncFreq.Numerator = 60;
    mode.MonitorVideoSignalInfo.vSyncFreq.Denominator = 1;
    mode.MonitorVideoSignalInfo.hSyncFreq.Numerator = 67500;
    mode.MonitorVideoSignalInfo.hSyncFreq.Denominator = 1;
    mode.MonitorVideoSignalInfo.pixelRate = 148500000;
    mode.MonitorVideoSignalInfo.scanLineOrdering = DISPLAYCONFIG_SCANLINE_ORDERING_PROGRESSIVE;

    pIn->pDefaultMonitorModes[0] = mode;
    pOut->DefaultMonitorModeBufferOutputCount = 1;
    pOut->PreferredMonitorModeIdx = 0;
    return STATUS_SUCCESS;
}

static DWORD WINAPI SwapChainThread(LPVOID param) {
    auto* mon = reinterpret_cast<MonitorContext*>(param);
    IDDCX_SWAPCHAIN swapchain = mon->swapchain_handle;

    while (mon->running) {
        IDARG_IN_SWAPCHAINSETDEVICE setDevice = {};
        setDevice.pDevice = nullptr;

        IDARG_OUT_RELEASEANDACQUIREBUFFER buf = {};
        HRESULT hr = IddCxSwapChainReleaseAndAcquireBuffer(swapchain, &buf);

        if (SUCCEEDED(hr)) {
            IddCxSwapChainFinishedProcessingFrame(swapchain);
        } else if (hr == E_PENDING) {
            HANDLE waitHandle = IddCxSwapChainGetDirtyTrackerCookie(swapchain);
            if (waitHandle)
                WaitForSingleObject(waitHandle, 16);
            else
                Sleep(16);
        } else {
            break;
        }
    }
    return 0;
}

static MonitorContext* FindMonitor(DeviceContext* ctx, IDDCX_MONITOR Monitor) {
    for (int i = 0; i < ctx->monitor_count; i++)
        if (ctx->monitors[i].monitor_handle == Monitor)
            return &ctx->monitors[i];
    return nullptr;
}

NTSTATUS EvtMonitorAssignSwapChain(IDDCX_MONITOR Monitor, const IDARG_IN_SETSWAPCHAIN* pIn) {
    // Scan all device contexts to find matching monitor (via parent back-pointer)
    // In practice, the first monitor's parent gives us the DeviceContext
    // We iterate to find which MonitorContext owns this IDDCX_MONITOR
    DeviceContext* device = nullptr;

    // Use WdfDeviceGetContext on the adapter's parent WDF device
    // IddCx objects are WDF children, so we walk up the object hierarchy
    WDFOBJECT parent = WdfObjectGetParentObject(Monitor);
    while (parent) {
        device = GetDeviceContext((WDFDEVICE)parent);
        if (device) break;
        parent = WdfObjectGetParentObject(parent);
    }
    if (!device) return STATUS_SUCCESS;

    auto* mon = FindMonitor(device, Monitor);
    if (mon) {
        mon->swapchain_handle = pIn->hSwapChain;
        mon->running = true;
        mon->thread_handle = CreateThread(
            nullptr, 0, SwapChainThread, mon, 0, nullptr);
    }

    return STATUS_SUCCESS;
}

NTSTATUS EvtMonitorUnassignSwapChain(IDDCX_MONITOR Monitor) {
    DeviceContext* device = nullptr;
    WDFOBJECT parent = WdfObjectGetParentObject(Monitor);
    while (parent) {
        device = GetDeviceContext((WDFDEVICE)parent);
        if (device) break;
        parent = WdfObjectGetParentObject(parent);
    }
    if (!device) return STATUS_SUCCESS;

    auto* mon = FindMonitor(device, Monitor);
    if (mon) {
        mon->running = false;
        if (mon->thread_handle) {
            WaitForSingleObject(mon->thread_handle, 1000);
            CloseHandle(mon->thread_handle);
            mon->thread_handle = nullptr;
        }
    }

    return STATUS_SUCCESS;
}
