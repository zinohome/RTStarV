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

NTSTATUS EvtMonitorAssignSwapChain(IDDCX_MONITOR Monitor, const IDARG_IN_SETSWAPCHAIN* pIn) {
    UNREFERENCED_PARAMETER(Monitor);
    UNREFERENCED_PARAMETER(pIn);
    return STATUS_SUCCESS;
}

NTSTATUS EvtMonitorUnassignSwapChain(IDDCX_MONITOR Monitor) {
    UNREFERENCED_PARAMETER(Monitor);
    return STATUS_SUCCESS;
}
