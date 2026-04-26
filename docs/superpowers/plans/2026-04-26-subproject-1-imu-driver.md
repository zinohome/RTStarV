# 子项目 1：IMU 驱动层 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 逆向 StarV View 的 USB IMU 协议，构建可在 Unity 中使用的 C++ 原生插件，实现头部姿态追踪（yaw/pitch/roll）。

**Architecture:** C++ 原生库通过 hidapi 与 StarV View 通信，读取 ICM-42688-P 的 6 轴原始数据，经互补滤波解算为欧拉角，通过 C ABI 暴露给 Unity 调用。

**Tech Stack:** C++17, hidapi, CMake, Python 3 (辅助分析工具), Unity 2022 LTS+

---

## 文件结构

```
RTStarV/
├── native/
│   ├── CMakeLists.txt                    # 构建配置
│   ├── include/
│   │   ├── rtstarv_imu.h                 # 公开 C ABI 头文件（Unity 调用）
│   │   └── imu_protocol.h               # IMU 协议定义（VID/PID/指令/数据格式）
│   ├── src/
│   │   ├── usb_device.cpp               # USB 设备枚举与连接
│   │   ├── imu_reader.cpp               # IMU 数据读取与解析
│   │   ├── attitude_solver.cpp          # 姿态解算（互补滤波）
│   │   └── rtstarv_imu.cpp             # C ABI 导出层
│   └── tests/
│       ├── test_attitude_solver.cpp     # 姿态解算单元测试
│       └── test_imu_parser.cpp          # IMU 数据解析单元测试
├── tools/
│   ├── usb_enumerate.py                 # USB 设备枚举脚本
│   ├── usb_dump.py                      # USB 原始数据抓取脚本
│   └── imu_visualizer.py               # IMU 数据实时可视化
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-26-rtstarv-ar-workspace-design.md
```

---

### Task 1: 项目基础搭建

**Files:**
- Create: `native/CMakeLists.txt`
- Create: `native/include/rtstarv_imu.h`
- Create: `native/src/rtstarv_imu.cpp`
- Create: `tools/usb_enumerate.py`
- Create: `.gitignore`

- [ ] **Step 1: 创建 .gitignore**

```gitignore
# Build
native/build/
*.o
*.so
*.dylib
*.dll

# IDE
.vscode/
.idea/
*.swp

# Unity (后续子项目会用到)
Library/
Temp/
Logs/
obj/
Build/

# Python
__pycache__/
*.pyc
venv/

# OS
.DS_Store
Thumbs.db
```

- [ ] **Step 2: 创建 CMakeLists.txt**

```cmake
cmake_minimum_required(VERSION 3.16)
project(rtstarv_imu VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(PkgConfig REQUIRED)
pkg_check_modules(HIDAPI REQUIRED hidapi-libusb)

add_library(rtstarv_imu SHARED
    src/rtstarv_imu.cpp
    src/usb_device.cpp
    src/imu_reader.cpp
    src/attitude_solver.cpp
)

target_include_directories(rtstarv_imu PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${HIDAPI_INCLUDE_DIRS}
)

target_link_libraries(rtstarv_imu PRIVATE ${HIDAPI_LIBRARIES})

# Tests
enable_testing()
add_executable(test_attitude_solver tests/test_attitude_solver.cpp src/attitude_solver.cpp)
target_include_directories(test_attitude_solver PRIVATE include)
add_test(NAME attitude_solver COMMAND test_attitude_solver)

add_executable(test_imu_parser tests/test_imu_parser.cpp src/imu_reader.cpp)
target_include_directories(test_imu_parser PRIVATE include ${HIDAPI_INCLUDE_DIRS})
target_link_libraries(test_imu_parser PRIVATE ${HIDAPI_LIBRARIES})
add_test(NAME imu_parser COMMAND test_imu_parser)
```

- [ ] **Step 3: 创建 C ABI 头文件 rtstarv_imu.h**

```cpp
#ifndef RTSTARV_IMU_H
#define RTSTARV_IMU_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef _WIN32
    #define RTSTARV_API __declspec(dllexport)
#else
    #define RTSTARV_API __attribute__((visibility("default")))
#endif

typedef struct {
    float yaw;
    float pitch;
    float roll;
} RTStarVAttitude;

typedef struct {
    int16_t accel_x, accel_y, accel_z;
    int16_t gyro_x, gyro_y, gyro_z;
    uint64_t timestamp_us;
} RTStarVRawIMU;

RTSTARV_API int rtstarv_init(void);
RTSTARV_API void rtstarv_shutdown(void);
RTSTARV_API int rtstarv_is_connected(void);
RTSTARV_API int rtstarv_get_attitude(RTStarVAttitude* attitude);
RTSTARV_API int rtstarv_get_raw(RTStarVRawIMU* raw);
RTSTARV_API void rtstarv_recenter(void);

#ifdef __cplusplus
}
#endif

#endif
```

- [ ] **Step 4: 创建空实现文件 rtstarv_imu.cpp（桩代码，后续 Task 填充）**

```cpp
#include "rtstarv_imu.h"

int rtstarv_init(void) { return -1; }
void rtstarv_shutdown(void) {}
int rtstarv_is_connected(void) { return 0; }
int rtstarv_get_attitude(RTStarVAttitude* attitude) { return -1; }
int rtstarv_get_raw(RTStarVRawIMU* raw) { return -1; }
void rtstarv_recenter(void) {}
```

- [ ] **Step 5: 创建 USB 枚举 Python 脚本 tools/usb_enumerate.py**

```python
#!/usr/bin/env python3
"""枚举所有 USB HID 设备，用于找到 StarV View 的 VID/PID。"""

import hid

def main():
    print("=== USB HID 设备列表 ===\n")
    devices = hid.enumerate()
    for d in devices:
        print(f"VID: 0x{d['vendor_id']:04x}  PID: 0x{d['product_id']:04x}")
        print(f"  Manufacturer: {d['manufacturer_string']}")
        print(f"  Product:      {d['product_string']}")
        print(f"  Interface:    {d['interface_number']}")
        print(f"  Path:         {d['path']}")
        print()

if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 安装依赖并验证构建**

Run:
```bash
# Python 依赖
pip install hidapi

# C++ 依赖 (Ubuntu/Debian)
sudo apt-get install libhidapi-dev pkg-config cmake

# 验证构建
cd native && mkdir -p build && cd build && cmake .. && make
```

Expected: 编译成功，生成 `librtstarv_imu.so`（桩实现）

- [ ] **Step 7: 提交**

```bash
git add .gitignore native/ tools/
git commit -m "feat: scaffold native IMU driver project with C ABI interface"
```

---

### Task 2: USB 设备发现 — 找到 StarV View 的 VID/PID

**Files:**
- Create: `native/include/imu_protocol.h`
- Create: `native/src/usb_device.cpp`

**前提：需要将 StarV View 眼镜通过 USB-C 连接到电脑。**

- [ ] **Step 1: 运行枚举脚本（眼镜未连接）**

Run:
```bash
python3 tools/usb_enumerate.py > /tmp/usb_before.txt
```

Expected: 记录当前所有 HID 设备列表

- [ ] **Step 2: 连接 StarV View，再次运行枚举脚本**

Run:
```bash
python3 tools/usb_enumerate.py > /tmp/usb_after.txt
```

- [ ] **Step 3: 对比找出新增设备**

Run:
```bash
diff /tmp/usb_before.txt /tmp/usb_after.txt
```

Expected: 找到 StarV View 的 VID、PID 和 interface number。记录下来。

- [ ] **Step 4: 创建协议头文件 imu_protocol.h**

```cpp
#ifndef IMU_PROTOCOL_H
#define IMU_PROTOCOL_H

#include <cstdint>

// 以下值需要根据 Step 3 的实际结果填写
namespace rtstarv {
namespace protocol {

constexpr uint16_t STARV_VIEW_VID = 0x0000; // TODO: 填入实际 VID
constexpr uint16_t STARV_VIEW_PID = 0x0000; // TODO: 填入实际 PID
constexpr int IMU_INTERFACE = -1;            // TODO: 填入实际 interface number

// IMU 激活指令（需要 Task 3 逆向确认）
constexpr uint8_t IMU_ACTIVATE_CMD[] = {0x00}; // TODO: 填入实际激活指令

// IMU 数据包格式（需要 Task 3 逆向确认）
constexpr size_t IMU_PACKET_SIZE = 64;         // TODO: 确认实际包大小

} // namespace protocol
} // namespace rtstarv

#endif
```

- [ ] **Step 5: 实现 usb_device.cpp — 设备发现和连接**

```cpp
#include "imu_protocol.h"
#include <hidapi/hidapi.h>
#include <cstdio>

namespace rtstarv {

class UsbDevice {
public:
    bool open() {
        handle_ = hid_open(protocol::STARV_VIEW_VID,
                           protocol::STARV_VIEW_PID, nullptr);
        if (!handle_) {
            fprintf(stderr, "StarV View not found (VID=0x%04x PID=0x%04x)\n",
                    protocol::STARV_VIEW_VID, protocol::STARV_VIEW_PID);
            return false;
        }
        hid_set_nonblocking(handle_, 1);
        return true;
    }

    void close() {
        if (handle_) {
            hid_close(handle_);
            handle_ = nullptr;
        }
    }

    bool is_open() const { return handle_ != nullptr; }

    int send(const uint8_t* data, size_t len) {
        if (!handle_) return -1;
        return hid_write(handle_, data, len);
    }

    int receive(uint8_t* buf, size_t len) {
        if (!handle_) return -1;
        return hid_read(handle_, buf, len);
    }

    ~UsbDevice() { close(); }

private:
    hid_device* handle_ = nullptr;
};

} // namespace rtstarv
```

- [ ] **Step 6: 提交**

```bash
git add native/include/imu_protocol.h native/src/usb_device.cpp
git commit -m "feat: USB device discovery and connection for StarV View"
```

---

### Task 3: 逆向 IMU 协议 — USB 抓包分析

**Files:**
- Create: `tools/usb_dump.py`
- Modify: `native/include/imu_protocol.h` (填入实际协议值)

**前提：需要一台 Android 手机安装 MYVU App，同时用 USB 抓包工具监听。**

- [ ] **Step 1: 创建 USB 原始数据抓取脚本 tools/usb_dump.py**

```python
#!/usr/bin/env python3
"""连接 StarV View 并持续 dump 所有 HID 数据包，用于分析 IMU 协议。"""

import hid
import sys
import time
import struct

# TODO: 填入 Task 2 找到的实际值
VID = 0x0000
PID = 0x0000

def main():
    print(f"Connecting to StarV View (VID=0x{VID:04x} PID=0x{PID:04x})...")

    device = hid.device()
    try:
        device.open(VID, PID)
    except IOError as e:
        print(f"Failed to open device: {e}")
        sys.exit(1)

    device.set_nonblocking(True)
    print("Connected. Dumping HID packets (Ctrl+C to stop)...\n")

    packet_count = 0
    try:
        while True:
            data = device.read(256)
            if data:
                packet_count += 1
                hex_str = " ".join(f"{b:02x}" for b in data)
                print(f"[{packet_count:6d}] ({len(data):3d} bytes) {hex_str}")
            else:
                time.sleep(0.001)
    except KeyboardInterrupt:
        print(f"\n\nTotal packets: {packet_count}")
    finally:
        device.close()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 不发送任何指令，直接运行 dump 脚本观察是否有数据**

Run:
```bash
python3 tools/usb_dump.py
```

Expected: 两种可能
- 有数据流出 → IMU 默认激活，直接分析数据格式
- 无数据 → 需要发送激活指令（继续 Step 3）

- [ ] **Step 3: 如果无数据，尝试参考 Xreal/Rokid 的已知激活指令**

参考已知的 AR 眼镜 IMU 激活模式：
- Xreal: `[0x02, 0x19, 0x01]`
- Rokid: 向 endpoint 0x02 发送特定序列

在 `usb_dump.py` 中添加发送尝试：

```python
# 尝试已知的激活指令
activate_sequences = [
    bytes([0x02, 0x19, 0x01]),           # Xreal style
    bytes([0x02, 0x01]),                  # Simplified
    bytes([0x01, 0x01]),                  # Generic enable
]

for seq in activate_sequences:
    print(f"Trying: {' '.join(f'{b:02x}' for b in seq)}")
    device.write(seq)
    time.sleep(0.5)
    data = device.read(256)
    if data:
        print(f"  -> Got response: {' '.join(f'{b:02x}' for b in data)}")
        break
    else:
        print(f"  -> No response")
```

- [ ] **Step 4: 分析数据包格式**

观察连续的 IMU 数据包，确认：
- 包头标识字节
- 加速度数据的偏移量和字节序（大端/小端）
- 陀螺仪数据的偏移量和字节序
- 时间戳位置（如有）
- 数据包总长度

ICM-42688-P 标准输出格式参考：
- 加速度：3 × int16，±16g 范围，灵敏度 2048 LSB/g
- 陀螺仪：3 × int16，±2000 dps 范围，灵敏度 16.4 LSB/dps

- [ ] **Step 5: 更新 imu_protocol.h — 填入逆向结果**

将 Step 2-4 的实际发现填入 `imu_protocol.h`：
- VID/PID 的实际值
- IMU 激活指令的实际字节
- 数据包大小和格式
- 各字段的偏移量

- [ ] **Step 6: 提交**

```bash
git add tools/usb_dump.py native/include/imu_protocol.h
git commit -m "feat: reverse-engineer StarV View IMU protocol"
```

---

### Task 4: IMU 数据读取与解析

**Files:**
- Create: `native/src/imu_reader.cpp`
- Create: `native/tests/test_imu_parser.cpp`

- [ ] **Step 1: 编写 IMU 解析测试 test_imu_parser.cpp**

```cpp
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cmath>

// 模拟一个 IMU 数据包（根据 Task 3 的逆向结果调整）
// 以下为示例格式，实际字段偏移需要根据逆向结果修改

struct IMUPacket {
    int16_t accel_x, accel_y, accel_z;
    int16_t gyro_x, gyro_y, gyro_z;
};

// 外部函数声明（imu_reader.cpp 中实现）
extern bool parse_imu_packet(const uint8_t* data, size_t len,
                             int16_t* ax, int16_t* ay, int16_t* az,
                             int16_t* gx, int16_t* gy, int16_t* gz);

void test_parse_valid_packet() {
    // 构造一个已知值的数据包
    // TODO: 根据 Task 3 逆向结果构造实际格式的测试数据
    uint8_t packet[64] = {0};

    // 假设加速度在偏移 4，小端序
    // accel_x = 2048 (1g), accel_y = 0, accel_z = 0
    packet[4] = 0x00; packet[5] = 0x08; // 2048 little-endian
    packet[6] = 0x00; packet[7] = 0x00;
    packet[8] = 0x00; packet[9] = 0x00;

    // gyro_x = 0, gyro_y = 0, gyro_z = 164 (10 dps)
    packet[10] = 0x00; packet[11] = 0x00;
    packet[12] = 0x00; packet[13] = 0x00;
    packet[14] = 0xA4; packet[15] = 0x00; // 164 little-endian

    int16_t ax, ay, az, gx, gy, gz;
    bool ok = parse_imu_packet(packet, 64, &ax, &ay, &az, &gx, &gy, &gz);

    assert(ok);
    assert(ax == 2048);
    assert(ay == 0);
    assert(az == 0);
    assert(gx == 0);
    assert(gy == 0);
    assert(gz == 164);

    printf("test_parse_valid_packet PASSED\n");
}

void test_parse_short_packet() {
    uint8_t packet[4] = {0};
    int16_t ax, ay, az, gx, gy, gz;
    bool ok = parse_imu_packet(packet, 4, &ax, &ay, &az, &gx, &gy, &gz);
    assert(!ok);
    printf("test_parse_short_packet PASSED\n");
}

int main() {
    test_parse_valid_packet();
    test_parse_short_packet();
    printf("\nAll IMU parser tests PASSED\n");
    return 0;
}
```

- [ ] **Step 2: 运行测试，验证失败（RED）**

Run: `cd native/build && cmake .. && make test_imu_parser && ./test_imu_parser`
Expected: 链接失败或断言失败（`parse_imu_packet` 未实现）

- [ ] **Step 3: 实现 imu_reader.cpp**

```cpp
#include "imu_protocol.h"
#include <cstdint>
#include <cstring>

namespace rtstarv {

bool parse_imu_packet(const uint8_t* data, size_t len,
                      int16_t* ax, int16_t* ay, int16_t* az,
                      int16_t* gx, int16_t* gy, int16_t* gz) {
    // TODO: 偏移量根据 Task 3 逆向结果调整
    constexpr size_t MIN_PACKET_SIZE = 16;
    constexpr size_t ACCEL_OFFSET = 4;
    constexpr size_t GYRO_OFFSET = 10;

    if (len < MIN_PACKET_SIZE) return false;

    auto read_i16_le = [](const uint8_t* p) -> int16_t {
        return static_cast<int16_t>(p[0] | (p[1] << 8));
    };

    const uint8_t* accel = data + ACCEL_OFFSET;
    *ax = read_i16_le(accel + 0);
    *ay = read_i16_le(accel + 2);
    *az = read_i16_le(accel + 4);

    const uint8_t* gyro = data + GYRO_OFFSET;
    *gx = read_i16_le(gyro + 0);
    *gy = read_i16_le(gyro + 2);
    *gz = read_i16_le(gyro + 4);

    return true;
}

class IMUReader {
public:
    IMUReader(UsbDevice& device) : device_(device) {}

    bool activate() {
        return device_.send(protocol::IMU_ACTIVATE_CMD,
                           sizeof(protocol::IMU_ACTIVATE_CMD)) > 0;
    }

    bool read_raw(int16_t* ax, int16_t* ay, int16_t* az,
                  int16_t* gx, int16_t* gy, int16_t* gz) {
        uint8_t buf[protocol::IMU_PACKET_SIZE];
        int bytes = device_.receive(buf, sizeof(buf));
        if (bytes <= 0) return false;
        return parse_imu_packet(buf, bytes, ax, ay, az, gx, gy, gz);
    }

private:
    UsbDevice& device_;
};

} // namespace rtstarv
```

- [ ] **Step 4: 运行测试，验证通过（GREEN）**

Run: `cd native/build && cmake .. && make test_imu_parser && ./test_imu_parser`
Expected: `All IMU parser tests PASSED`

- [ ] **Step 5: 提交**

```bash
git add native/src/imu_reader.cpp native/tests/test_imu_parser.cpp
git commit -m "feat: IMU packet parser with unit tests"
```

---

### Task 5: 姿态解算 — 互补滤波

**Files:**
- Create: `native/src/attitude_solver.cpp`
- Create: `native/tests/test_attitude_solver.cpp`

- [ ] **Step 1: 编写姿态解算测试 test_attitude_solver.cpp**

```cpp
#include <cassert>
#include <cstdio>
#include <cmath>

// 外部函数声明
struct Attitude { float yaw, pitch, roll; };

class AttitudeSolver {
public:
    AttitudeSolver(float alpha = 0.98f, float lpf_cutoff_hz = 12.0f);
    void update(int16_t ax, int16_t ay, int16_t az,
                int16_t gx, int16_t gy, int16_t gz,
                float dt_seconds);
    Attitude get() const;
    void recenter();
};

constexpr float DEG_EPS = 0.5f;

void test_initial_state() {
    AttitudeSolver solver;
    Attitude att = solver.get();
    assert(fabs(att.yaw) < DEG_EPS);
    assert(fabs(att.pitch) < DEG_EPS);
    assert(fabs(att.roll) < DEG_EPS);
    printf("test_initial_state PASSED\n");
}

void test_static_level() {
    AttitudeSolver solver;
    // 静止放平：accel = (0, 0, 2048)即1g朝下, gyro = (0,0,0)
    for (int i = 0; i < 100; i++) {
        solver.update(0, 0, 2048, 0, 0, 0, 0.0025f); // 400Hz
    }
    Attitude att = solver.get();
    assert(fabs(att.pitch) < 2.0f);
    assert(fabs(att.roll) < 2.0f);
    printf("test_static_level PASSED\n");
}

void test_recenter() {
    AttitudeSolver solver;
    // 先模拟头部向右转 30°
    // gyro_z = 30°/s * 16.4 LSB/(°/s) = 492 LSB, 持续 1 秒
    for (int i = 0; i < 400; i++) {
        solver.update(0, 0, 2048, 0, 0, 492, 0.0025f);
    }
    Attitude before = solver.get();
    assert(fabs(before.yaw) > 10.0f); // 应该有明显偏转

    solver.recenter();
    Attitude after = solver.get();
    assert(fabs(after.yaw) < DEG_EPS);
    assert(fabs(after.pitch) < DEG_EPS);
    printf("test_recenter PASSED\n");
}

int main() {
    test_initial_state();
    test_static_level();
    test_recenter();
    printf("\nAll attitude solver tests PASSED\n");
    return 0;
}
```

- [ ] **Step 2: 运行测试，验证失败（RED）**

Run: `cd native/build && cmake .. && make test_attitude_solver && ./test_attitude_solver`
Expected: 编译失败（AttitudeSolver 未实现）

- [ ] **Step 3: 实现 attitude_solver.cpp**

```cpp
#include <cmath>
#include <cstdint>

namespace rtstarv {

struct Attitude {
    float yaw = 0.0f;
    float pitch = 0.0f;
    float roll = 0.0f;
};

class AttitudeSolver {
public:
    AttitudeSolver(float alpha = 0.98f, float lpf_cutoff_hz = 12.0f)
        : alpha_(alpha), lpf_cutoff_hz_(lpf_cutoff_hz) {}

    void update(int16_t ax, int16_t ay, int16_t az,
                int16_t gx, int16_t gy, int16_t gz,
                float dt) {
        constexpr float ACCEL_SCALE = 1.0f / 2048.0f;  // ±16g → 2048 LSB/g
        constexpr float GYRO_SCALE = 1.0f / 16.4f;     // ±2000 dps → 16.4 LSB/dps
        constexpr float RAD_TO_DEG = 180.0f / M_PI;

        float fax = ax * ACCEL_SCALE;
        float fay = ay * ACCEL_SCALE;
        float faz = az * ACCEL_SCALE;

        float gyro_yaw_dps   = gz * GYRO_SCALE;
        float gyro_pitch_dps = gx * GYRO_SCALE;
        float gyro_roll_dps  = gy * GYRO_SCALE;

        // 加速度计算的 pitch/roll
        float accel_pitch = atan2f(fax, sqrtf(fay * fay + faz * faz)) * RAD_TO_DEG;
        float accel_roll  = atan2f(fay, sqrtf(fax * fax + faz * faz)) * RAD_TO_DEG;

        // 互补滤波
        raw_pitch_ = alpha_ * (raw_pitch_ + gyro_pitch_dps * dt) + (1.0f - alpha_) * accel_pitch;
        raw_roll_  = alpha_ * (raw_roll_ + gyro_roll_dps * dt) + (1.0f - alpha_) * accel_roll;
        raw_yaw_  += gyro_yaw_dps * dt; // yaw 只能用陀螺仪积分

        // 低通滤波
        float rc = 1.0f / (2.0f * M_PI * lpf_cutoff_hz_);
        float a = dt / (rc + dt);
        filtered_yaw_   = filtered_yaw_   + a * (raw_yaw_ - filtered_yaw_);
        filtered_pitch_ = filtered_pitch_ + a * (raw_pitch_ - filtered_pitch_);
        filtered_roll_  = filtered_roll_  + a * (raw_roll_ - filtered_roll_);
    }

    Attitude get() const {
        return {
            filtered_yaw_ - center_yaw_,
            filtered_pitch_ - center_pitch_,
            filtered_roll_ - center_roll_
        };
    }

    void recenter() {
        center_yaw_ = filtered_yaw_;
        center_pitch_ = filtered_pitch_;
        center_roll_ = filtered_roll_;
    }

private:
    float alpha_;
    float lpf_cutoff_hz_;

    float raw_yaw_ = 0.0f, raw_pitch_ = 0.0f, raw_roll_ = 0.0f;
    float filtered_yaw_ = 0.0f, filtered_pitch_ = 0.0f, filtered_roll_ = 0.0f;
    float center_yaw_ = 0.0f, center_pitch_ = 0.0f, center_roll_ = 0.0f;
};

} // namespace rtstarv
```

- [ ] **Step 4: 运行测试，验证通过（GREEN）**

Run: `cd native/build && cmake .. && make test_attitude_solver && ./test_attitude_solver`
Expected: `All attitude solver tests PASSED`

- [ ] **Step 5: 提交**

```bash
git add native/src/attitude_solver.cpp native/tests/test_attitude_solver.cpp
git commit -m "feat: attitude solver with complementary filter and low-pass smoothing"
```

---

### Task 6: C ABI 导出层 — 串联全部模块

**Files:**
- Modify: `native/src/rtstarv_imu.cpp`

- [ ] **Step 1: 实现完整的 rtstarv_imu.cpp**

```cpp
#include "rtstarv_imu.h"
#include "imu_protocol.h"
#include <memory>

// 引入内部实现（在实际构建中通过头文件引用）
namespace rtstarv {
    class UsbDevice; // from usb_device.cpp
    class IMUReader;  // from imu_reader.cpp
    class AttitudeSolver; // from attitude_solver.cpp
}

static std::unique_ptr<rtstarv::UsbDevice> g_device;
static std::unique_ptr<rtstarv::IMUReader> g_reader;
static std::unique_ptr<rtstarv::AttitudeSolver> g_solver;
static bool g_initialized = false;
static uint64_t g_last_time_us = 0;

int rtstarv_init(void) {
    if (g_initialized) return 0;

    if (hid_init() != 0) return -1;

    g_device = std::make_unique<rtstarv::UsbDevice>();
    if (!g_device->open()) {
        hid_exit();
        return -1;
    }

    g_reader = std::make_unique<rtstarv::IMUReader>(*g_device);
    if (!g_reader->activate()) {
        g_device->close();
        hid_exit();
        return -1;
    }

    g_solver = std::make_unique<rtstarv::AttitudeSolver>(0.98f, 12.0f);
    g_initialized = true;
    g_last_time_us = 0;
    return 0;
}

void rtstarv_shutdown(void) {
    if (!g_initialized) return;
    g_reader.reset();
    g_device.reset();
    g_solver.reset();
    hid_exit();
    g_initialized = false;
}

int rtstarv_is_connected(void) {
    return g_initialized && g_device && g_device->is_open() ? 1 : 0;
}

int rtstarv_get_attitude(RTStarVAttitude* attitude) {
    if (!g_initialized || !attitude) return -1;

    int16_t ax, ay, az, gx, gy, gz;
    if (!g_reader->read_raw(&ax, &ay, &az, &gx, &gy, &gz)) return -1;

    // 计算时间增量（首次使用默认 2.5ms = 400Hz）
    float dt = 0.0025f;
    // TODO: 如果数据包包含时间戳，使用实际 dt

    g_solver->update(ax, ay, az, gx, gy, gz, dt);
    auto att = g_solver->get();
    attitude->yaw = att.yaw;
    attitude->pitch = att.pitch;
    attitude->roll = att.roll;
    return 0;
}

int rtstarv_get_raw(RTStarVRawIMU* raw) {
    if (!g_initialized || !raw) return -1;

    int16_t ax, ay, az, gx, gy, gz;
    if (!g_reader->read_raw(&ax, &ay, &az, &gx, &gy, &gz)) return -1;

    raw->accel_x = ax; raw->accel_y = ay; raw->accel_z = az;
    raw->gyro_x = gx;  raw->gyro_y = gy;  raw->gyro_z = gz;
    raw->timestamp_us = 0; // TODO: 填入实际时间戳
    return 0;
}

void rtstarv_recenter(void) {
    if (g_solver) g_solver->recenter();
}
```

- [ ] **Step 2: 构建完整库**

Run: `cd native/build && cmake .. && make`
Expected: `librtstarv_imu.so` 编译成功，无错误

- [ ] **Step 3: 运行所有测试**

Run: `cd native/build && ctest --output-on-failure`
Expected: 所有测试通过

- [ ] **Step 4: 提交**

```bash
git add native/src/rtstarv_imu.cpp
git commit -m "feat: complete C ABI export layer linking all IMU modules"
```

---

### Task 7: 实时可视化验证工具

**Files:**
- Create: `tools/imu_visualizer.py`

- [ ] **Step 1: 创建 IMU 数据实时可视化脚本**

```python
#!/usr/bin/env python3
"""实时可视化 StarV View 的 IMU 姿态数据，用于验证驱动正确性。"""

import ctypes
import time
import sys
import os

# 加载原生库
lib_path = os.path.join(os.path.dirname(__file__), "../native/build/librtstarv_imu.so")
lib = ctypes.CDLL(lib_path)

class Attitude(ctypes.Structure):
    _fields_ = [("yaw", ctypes.c_float),
                 ("pitch", ctypes.c_float),
                 ("roll", ctypes.c_float)]

lib.rtstarv_init.restype = ctypes.c_int
lib.rtstarv_shutdown.restype = None
lib.rtstarv_get_attitude.restype = ctypes.c_int
lib.rtstarv_get_attitude.argtypes = [ctypes.POINTER(Attitude)]
lib.rtstarv_recenter.restype = None

def main():
    print("Initializing StarV View IMU driver...")
    if lib.rtstarv_init() != 0:
        print("ERROR: Failed to init. Is StarV View connected?")
        sys.exit(1)

    print("Connected! Reading attitude data (Ctrl+C to stop, R to recenter)\n")
    att = Attitude()

    try:
        while True:
            if lib.rtstarv_get_attitude(ctypes.byref(att)) == 0:
                bar_yaw = "=" * max(0, min(40, int(20 + att.yaw / 2)))
                sys.stdout.write(
                    f"\rYaw: {att.yaw:+7.1f}°  "
                    f"Pitch: {att.pitch:+7.1f}°  "
                    f"Roll: {att.roll:+7.1f}°  "
                    f"[{bar_yaw:<40s}]"
                )
                sys.stdout.flush()
            time.sleep(0.008)  # ~120Hz display
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        lib.rtstarv_shutdown()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 连接 StarV View 并运行可视化**

Run: `python3 tools/imu_visualizer.py`
Expected: 终端实时显示 yaw/pitch/roll 数值，转动头部时数值相应变化

- [ ] **Step 3: 验证以下行为**

- 左右转头 → yaw 变化
- 上下点头 → pitch 变化
- 左右歪头 → roll 变化
- 数据平滑，无明显抖动
- 响应及时，无明显延迟

- [ ] **Step 4: 提交**

```bash
git add tools/imu_visualizer.py
git commit -m "feat: real-time IMU attitude visualizer for driver validation"
```

---

## 自检

**Spec 覆盖：**
- ✅ 逆向 StarV View USB IMU 协议（Task 2, 3）
- ✅ C++ hidapi 原生插件（Task 1, 2, 5, 6）
- ✅ 姿态解算 + 滤波（Task 5）
- ✅ C ABI 接口供 Unity 调用（Task 1, 6）
- ✅ 验证工具（Task 7）

**占位符：**
- `imu_protocol.h` 中的 VID/PID/激活指令标记为 TODO — 这是正确的，必须通过 Task 2/3 的逆向工程获得实际值。

**类型一致性：**
- `RTStarVAttitude` (C ABI) ↔ `Attitude` (C++ internal) — 字段一致 (yaw/pitch/roll)
- `parse_imu_packet` 参数签名全文一致
- `AttitudeSolver::update` 参数签名全文一致
