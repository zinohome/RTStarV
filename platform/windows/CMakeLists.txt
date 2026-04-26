cmake_minimum_required(VERSION 3.16)
project(RTStarV VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# hidapi 源码编译
set(HIDAPI_SRC ${CMAKE_CURRENT_SOURCE_DIR}/third_party/hidapi/windows/hid.c)

# 主应用源文件
set(SOURCES
    src/main.cpp
    src/app.cpp
    src/d3d11_renderer.cpp
    src/screen_quad.cpp
    src/screen_layout.cpp
    src/screen_capture.cpp
    src/virtual_display.cpp
    src/hotkey_manager.cpp
    src/tray_icon.cpp
    ${HIDAPI_SRC}
    # 共享核心
    ../../native/src/imu_parser.cpp
    ../../native/src/attitude_solver.cpp
    ../../native/src/usb_device.cpp
    ../../native/src/imu_reader.cpp
    ../../native/src/rtstarv_imu.cpp
)

add_executable(RTStarV WIN32 ${SOURCES} resources/app.rc)

target_include_directories(RTStarV PRIVATE
    src
    ../../native/include
    ../../native/src
    third_party/hidapi/hidapi
)

target_link_libraries(RTStarV PRIVATE
    d3d11 dxgi d3dcompiler
    hid setupapi
    shell32 user32 gdi32 ole32
)

target_compile_definitions(RTStarV PRIVATE
    UNICODE _UNICODE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
)
