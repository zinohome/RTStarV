// platform/windows/src/math_utils.h
#pragma once
#include <cmath>
#include <array>

namespace rtstarv {

struct Vec3 { float x, y, z; };
struct Vec4 { float x, y, z, w; };

using Mat4 = std::array<float, 16>; // column-major

constexpr float DEG2RAD = 3.14159265358979f / 180.0f;

inline Mat4 mat4_identity() {
    return {1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1};
}

inline Mat4 mat4_multiply(const Mat4& a, const Mat4& b) {
    Mat4 r{};
    for (int c = 0; c < 4; c++)
        for (int row = 0; row < 4; row++)
            for (int k = 0; k < 4; k++)
                r[c * 4 + row] += a[k * 4 + row] * b[c * 4 + k];
    return r;
}

inline Mat4 mat4_rotation_x(float rad) {
    float c = cosf(rad), s = sinf(rad);
    return {1,0,0,0, 0,c,s,0, 0,-s,c,0, 0,0,0,1};
}

inline Mat4 mat4_rotation_y(float rad) {
    float c = cosf(rad), s = sinf(rad);
    return {c,0,-s,0, 0,1,0,0, s,0,c,0, 0,0,0,1};
}

inline Mat4 mat4_rotation_z(float rad) {
    float c = cosf(rad), s = sinf(rad);
    return {c,s,0,0, -s,c,0,0, 0,0,1,0, 0,0,0,1};
}

inline Mat4 mat4_translation(float x, float y, float z) {
    return {1,0,0,0, 0,1,0,0, 0,0,1,0, x,y,z,1};
}

inline Mat4 mat4_perspective(float fov_deg, float aspect, float near_z, float far_z) {
    float f = 1.0f / tanf(fov_deg * DEG2RAD * 0.5f);
    float range = far_z / (near_z - far_z);
    return {
        f / aspect, 0, 0, 0,
        0, f, 0, 0,
        0, 0, range, -1,
        0, 0, range * near_z, 0
    };
}

// 球面坐标 (yaw_deg, pitch_deg, radius) -> 世界坐标
inline Vec3 spherical_to_cartesian(float yaw_deg, float pitch_deg, float radius) {
    float yaw = yaw_deg * DEG2RAD;
    float pitch = pitch_deg * DEG2RAD;
    return {
        radius * sinf(yaw) * cosf(pitch),
        radius * sinf(pitch),
        -radius * cosf(yaw) * cosf(pitch) // -Z 朝前
    };
}

inline float lerp(float a, float b, float t) { return a + (b - a) * t; }

} // namespace rtstarv
