#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#if defined(_WIN32)
    #define RTSTARV_API __declspec(dllexport)
#else
    #define RTSTARV_API __attribute__((visibility("default")))
#endif

typedef struct {
    float acc_x, acc_y, acc_z;   // m/s²
    float gyr_x, gyr_y, gyr_z;  // rad/s
    uint32_t timestamp;
    uint8_t  sequence;
    uint8_t  has_mag;
    float mag_x, mag_y, mag_z;   // µT
    uint32_t mag_timestamp;
} RTStarVImuData;

typedef struct {
    float yaw, pitch, roll;      // degrees
} RTStarVAttitude;

// 初始化驱动，连接设备。返回 0=成功, -1=失败
RTSTARV_API int rtstarv_init(void);

// 关闭设备，释放资源
RTSTARV_API void rtstarv_shutdown(void);

// 设备是否已连接
RTSTARV_API int rtstarv_is_connected(void);

// 启动 IMU 数据流。freq_hz: 12/25/50/100/200, enable_mag: 0/1
RTSTARV_API int rtstarv_start(int freq_hz, int enable_mag);

// 停止 IMU 数据流
RTSTARV_API void rtstarv_stop(void);

// 获取最新 IMU 原始数据。返回 0=有数据, -1=无数据
RTSTARV_API int rtstarv_get_imu(RTStarVImuData* out);

// 获取姿态角。返回 0=有数据, -1=无数据
RTSTARV_API int rtstarv_get_attitude(RTStarVAttitude* out);

// 重置航向参考点（一键居中）
RTSTARV_API void rtstarv_recenter(void);

// 获取丢帧数
RTSTARV_API uint32_t rtstarv_dropped_frames(void);

#ifdef __cplusplus
}
#endif
