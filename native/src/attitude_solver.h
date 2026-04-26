#pragma once

#include "imu_parser.h"
#include <chrono>

namespace rtstarv {

struct Attitude {
    float yaw   = 0.0f;  // degrees
    float pitch = 0.0f;
    float roll  = 0.0f;
};

// 互补滤波姿态解算器
class AttitudeSolver {
public:
    void update(const ImuSample& sample);
    Attitude get() const;

    // 记录当前姿态为零点，后续输出相对于此零点
    void recenter();

private:
    float pitch_ = 0.0f;  // rad
    float roll_  = 0.0f;  // rad
    float yaw_   = 0.0f;  // rad

    float ref_yaw_   = 0.0f;
    float ref_pitch_ = 0.0f;
    float ref_roll_  = 0.0f;
    bool has_ref_ = false;

    bool first_ = true;
    std::chrono::steady_clock::time_point last_time_;

    static constexpr float ALPHA = 0.98f;
    static constexpr float RAD2DEG = 57.29577951308232f;
};

} // namespace rtstarv
