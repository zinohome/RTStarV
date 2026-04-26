// platform/windows/src/app.h
#pragma once
#include <windows.h>
#include <cstdint>

// 前向声明
namespace rtstarv { class UsbDevice; class ImuReader; class AttitudeSolver; }

enum class LayoutMode { Single = 1, Triple = 3, Hex = 6 };

struct AppState {
    bool running = true;
    bool imu_connected = false;
    LayoutMode layout = LayoutMode::Single;
    int focus_screen = 0;
    float cam_yaw = 0, cam_pitch = 0, cam_roll = 0;
};

class App {
public:
    bool init(HINSTANCE hInstance);
    void run();
    void shutdown();

    void on_hotkey(int id);
    void on_tray_command(int cmd);

    AppState& state() { return state_; }

private:
    void update();
    void render();

    AppState state_;
    HWND hwnd_ = nullptr;
    HINSTANCE hinstance_ = nullptr;

    // 模块指针（在 app.cpp 中管理生命周期）
    struct Modules;
    Modules* modules_ = nullptr;
};
