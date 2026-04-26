#include "attitude_solver.h"
#include <cmath>

namespace rtstarv {

void AttitudeSolver::update(const ImuSample& sample) {
    auto now = std::chrono::steady_clock::now();

    if (first_) {
        // 用加速度计初始化 pitch/roll
        pitch_ = std::atan2(sample.acc_x,
                    std::sqrt(sample.acc_y * sample.acc_y + sample.acc_z * sample.acc_z));
        roll_ = std::atan2(sample.acc_y,
                    std::sqrt(sample.acc_x * sample.acc_x + sample.acc_z * sample.acc_z));
        yaw_ = 0.0f;
        last_time_ = now;
        first_ = false;
        return;
    }

    float dt = std::chrono::duration<float>(now - last_time_).count();
    last_time_ = now;

    if (dt <= 0.0f || dt > 0.1f) return;  // 跳过异常间隔

    // 陀螺仪积分
    float gyr_pitch = pitch_ + sample.gyr_x * dt;
    float gyr_roll  = roll_  + sample.gyr_y * dt;
    yaw_ += sample.gyr_z * dt;

    // 加速度计倾斜角
    float acc_pitch = std::atan2(sample.acc_x,
                        std::sqrt(sample.acc_y * sample.acc_y + sample.acc_z * sample.acc_z));
    float acc_roll  = std::atan2(sample.acc_y,
                        std::sqrt(sample.acc_x * sample.acc_x + sample.acc_z * sample.acc_z));

    // 互补滤波
    pitch_ = ALPHA * gyr_pitch + (1.0f - ALPHA) * acc_pitch;
    roll_  = ALPHA * gyr_roll  + (1.0f - ALPHA) * acc_roll;
}

Attitude AttitudeSolver::get() const {
    Attitude a;
    a.yaw   = (yaw_   - ref_yaw_)   * RAD2DEG;
    a.pitch = (pitch_ - ref_pitch_) * RAD2DEG;
    a.roll  = (roll_  - ref_roll_)  * RAD2DEG;
    return a;
}

void AttitudeSolver::recenter() {
    ref_yaw_   = yaw_;
    ref_pitch_ = pitch_;
    ref_roll_  = roll_;
    has_ref_ = true;
}

} // namespace rtstarv
