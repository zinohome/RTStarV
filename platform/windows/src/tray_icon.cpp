// platform/windows/src/tray_icon.cpp
#include "tray_icon.h"
#include "app.h"

#define WM_TRAYICON (WM_APP + 1)
#define ID_TRAY_RECENTER  4001
#define ID_TRAY_1SCREEN   4002
#define ID_TRAY_3SCREEN   4003
#define ID_TRAY_6SCREEN   4004
#define ID_TRAY_EXIT      4005

bool TrayIcon::init(HWND hwnd, HINSTANCE hInstance) {
    nid_.cbSize = sizeof(nid_);
    nid_.hWnd = hwnd;
    nid_.uID = 1;
    nid_.uFlags = NIF_ICON | NIF_MESSAGE | NIF_TIP;
    nid_.uCallbackMessage = WM_TRAYICON;
    nid_.hIcon = LoadIcon(hInstance, MAKEINTRESOURCE(101));
    if (!nid_.hIcon) nid_.hIcon = LoadIcon(nullptr, IDI_APPLICATION);
    wcscpy_s(nid_.szTip, L"RTStarV AR Workspace");

    Shell_NotifyIconW(NIM_ADD, &nid_);
    created_ = true;
    return true;
}

void TrayIcon::destroy() {
    if (created_) {
        Shell_NotifyIconW(NIM_DELETE, &nid_);
        created_ = false;
    }
}

void TrayIcon::show_menu(HWND hwnd, LayoutMode current_layout) {
    HMENU menu = CreatePopupMenu();
    AppendMenuW(menu, MF_STRING, ID_TRAY_RECENTER, L"居中 (&C)");
    AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(menu, MF_STRING | (current_layout == LayoutMode::Single ? MF_CHECKED : 0),
                ID_TRAY_1SCREEN, L"1 屏 (&1)");
    AppendMenuW(menu, MF_STRING | (current_layout == LayoutMode::Triple ? MF_CHECKED : 0),
                ID_TRAY_3SCREEN, L"3 屏 (&3)");
    AppendMenuW(menu, MF_STRING | (current_layout == LayoutMode::Hex ? MF_CHECKED : 0),
                ID_TRAY_6SCREEN, L"6 屏 (&6)");
    AppendMenuW(menu, MF_SEPARATOR, 0, nullptr);
    AppendMenuW(menu, MF_STRING, ID_TRAY_EXIT, L"退出 (&Q)");

    POINT pt;
    GetCursorPos(&pt);
    SetForegroundWindow(hwnd);
    int cmd = TrackPopupMenu(menu, TPM_RETURNCMD | TPM_NONOTIFY, pt.x, pt.y, 0, hwnd, nullptr);
    DestroyMenu(menu);

    switch (cmd) {
    case ID_TRAY_RECENTER: PostMessageW(hwnd, WM_HOTKEY, 0, 0); break;
    case ID_TRAY_1SCREEN:  PostMessageW(hwnd, WM_HOTKEY, 1, 0); break;
    case ID_TRAY_3SCREEN:  PostMessageW(hwnd, WM_HOTKEY, 3, 0); break;
    case ID_TRAY_6SCREEN:  PostMessageW(hwnd, WM_HOTKEY, 6, 0); break;
    case ID_TRAY_EXIT:     PostQuitMessage(0); break;
    }
}
