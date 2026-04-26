// platform/windows/src/virtual_display.h
#pragma once
#include <windows.h>

class VirtualDisplay {
public:
    bool init();
    void destroy();
    bool add_monitor(int width = 1920, int height = 1080);
    bool remove_monitor();
    int monitor_count() const { return count_; }
    bool is_available() const { return handle_ != INVALID_HANDLE_VALUE; }

private:
    HANDLE handle_ = INVALID_HANDLE_VALUE;
    int count_ = 0;
};
