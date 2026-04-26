// platform/windows/src/screen_layout.h
#pragma once
#include "math_utils.h"
#include "d3d11_renderer.h"
#include <vector>

enum class LayoutMode;

class ScreenLayout {
public:
    void set_mode(LayoutMode mode);
    void update(float dt);
    void recenter();

    const std::vector<ScreenTransform>& get_screens() const { return current_; }

private:
    static std::vector<ScreenTransform> compute_layout(LayoutMode mode);

    std::vector<ScreenTransform> current_;
    std::vector<ScreenTransform> target_;
    float anim_t_ = 1.0f;
    static constexpr float ANIM_DURATION = 0.3f;
    static constexpr float SCREEN_RADIUS = 5.0f;
    static constexpr float SCREEN_WIDTH = 2.8f;
    static constexpr float SCREEN_HEIGHT = 1.575f;
};
