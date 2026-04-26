// platform/windows/src/screen_layout.cpp
#include "screen_layout.h"
#include "app.h"
#include <algorithm>

std::vector<ScreenTransform> ScreenLayout::compute_layout(LayoutMode mode) {
    std::vector<ScreenTransform> screens;

    auto make_screen = [](float yaw_deg, float pitch_deg) -> ScreenTransform {
        ScreenTransform s;
        s.position = rtstarv::spherical_to_cartesian(yaw_deg, pitch_deg, SCREEN_RADIUS);
        s.yaw_deg = yaw_deg;
        s.pitch_deg = pitch_deg;
        s.width = SCREEN_WIDTH;
        s.height = SCREEN_HEIGHT;
        return s;
    };

    switch (mode) {
    case LayoutMode::Single:
        screens.push_back(make_screen(0, 0));
        break;
    case LayoutMode::Triple:
        screens.push_back(make_screen(-35, 0));
        screens.push_back(make_screen(0, 0));
        screens.push_back(make_screen(35, 0));
        break;
    case LayoutMode::Hex:
        for (float pitch : {12.5f, -12.5f})
            for (float yaw : {-35.0f, 0.0f, 35.0f})
                screens.push_back(make_screen(yaw, pitch));
        break;
    }
    return screens;
}

void ScreenLayout::set_mode(LayoutMode mode) {
    target_ = compute_layout(mode);

    if (current_.empty()) {
        current_ = target_;
        anim_t_ = 1.0f;
        return;
    }

    while (current_.size() < target_.size())
        current_.push_back(target_[current_.size()]);
    while (current_.size() > target_.size())
        current_.pop_back();

    anim_t_ = 0.0f;
}

void ScreenLayout::update(float dt) {
    if (anim_t_ >= 1.0f) return;

    anim_t_ = std::min(1.0f, anim_t_ + dt / ANIM_DURATION);
    float t = anim_t_ * anim_t_ * (3.0f - 2.0f * anim_t_); // smoothstep

    for (size_t i = 0; i < current_.size() && i < target_.size(); i++) {
        current_[i].position.x = rtstarv::lerp(current_[i].position.x, target_[i].position.x, t);
        current_[i].position.y = rtstarv::lerp(current_[i].position.y, target_[i].position.y, t);
        current_[i].position.z = rtstarv::lerp(current_[i].position.z, target_[i].position.z, t);
        current_[i].yaw_deg = rtstarv::lerp(current_[i].yaw_deg, target_[i].yaw_deg, t);
        current_[i].pitch_deg = rtstarv::lerp(current_[i].pitch_deg, target_[i].pitch_deg, t);
    }

    if (anim_t_ >= 1.0f)
        current_ = target_;
}

void ScreenLayout::recenter() {
    // IMU recenter 后 cam_yaw/pitch=0，屏幕自然在正前方
}
