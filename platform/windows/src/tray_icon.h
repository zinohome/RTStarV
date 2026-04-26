// platform/windows/src/tray_icon.h
#pragma once
#include <windows.h>
#include <shellapi.h>

enum class LayoutMode;

class TrayIcon {
public:
    bool init(HWND hwnd, HINSTANCE hInstance);
    void destroy();
    void show_menu(HWND hwnd, LayoutMode current_layout);

private:
    NOTIFYICONDATAW nid_ = {};
    bool created_ = false;
};
