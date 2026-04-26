// platform/windows/src/hotkey_manager.h
#pragma once
#include <windows.h>

class HotkeyManager {
public:
    bool init(HWND hwnd);
    void destroy();
private:
    HWND hwnd_ = nullptr;
};
