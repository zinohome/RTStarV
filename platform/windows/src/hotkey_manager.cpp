// platform/windows/src/hotkey_manager.cpp
#include "hotkey_manager.h"

bool HotkeyManager::init(HWND hwnd) {
    hwnd_ = hwnd;
    RegisterHotKey(hwnd, 0,  MOD_CONTROL | MOD_SHIFT, VK_SPACE);  // 居中
    RegisterHotKey(hwnd, 1,  MOD_CONTROL | MOD_SHIFT, '1');        // 1屏
    RegisterHotKey(hwnd, 3,  MOD_CONTROL | MOD_SHIFT, '3');        // 3屏
    RegisterHotKey(hwnd, 6,  MOD_CONTROL | MOD_SHIFT, '6');        // 6屏
    RegisterHotKey(hwnd, 10, MOD_CONTROL | MOD_SHIFT, VK_LEFT);   // 焦点左
    RegisterHotKey(hwnd, 11, MOD_CONTROL | MOD_SHIFT, VK_RIGHT);  // 焦点右
    RegisterHotKey(hwnd, 12, MOD_CONTROL | MOD_SHIFT, VK_UP);     // 焦点上
    RegisterHotKey(hwnd, 13, MOD_CONTROL | MOD_SHIFT, VK_DOWN);   // 焦点下
    return true;
}

void HotkeyManager::destroy() {
    if (!hwnd_) return;
    for (int id : {0, 1, 3, 6, 10, 11, 12, 13})
        UnregisterHotKey(hwnd_, id);
}
