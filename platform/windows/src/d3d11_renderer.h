// platform/windows/src/d3d11_renderer.h
#pragma once
#include "math_utils.h"
#include <d3d11.h>
#include <dxgi1_2.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;

struct ScreenTransform {
    rtstarv::Vec3 position;   // 世界坐标
    float yaw_deg;             // 朝向（面向原点则不需要额外旋转）
    float pitch_deg;
    float width;               // 世界空间中的宽度
    float height;
};

class D3D11Renderer {
public:
    bool init(HWND hwnd, int width, int height);
    void destroy();

    void begin_frame(float r, float g, float b, float a);
    void set_camera(float yaw_deg, float pitch_deg, float roll_deg);
    void draw_screen_quad(const ScreenTransform& screen, ID3D11ShaderResourceView* texture, bool focused);
    void end_frame();

    ID3D11Device* device() const { return device_.Get(); }
    ID3D11DeviceContext* context() const { return context_.Get(); }

private:
    bool create_shaders();
    bool create_quad_geometry();

    ComPtr<ID3D11Device> device_;
    ComPtr<ID3D11DeviceContext> context_;
    ComPtr<IDXGISwapChain1> swap_chain_;
    ComPtr<ID3D11RenderTargetView> rtv_;
    ComPtr<ID3D11VertexShader> vs_;
    ComPtr<ID3D11PixelShader> ps_;
    ComPtr<ID3D11InputLayout> input_layout_;
    ComPtr<ID3D11Buffer> vertex_buffer_;
    ComPtr<ID3D11Buffer> index_buffer_;
    ComPtr<ID3D11Buffer> constant_buffer_;
    ComPtr<ID3D11SamplerState> sampler_;
    ComPtr<ID3D11Texture2D> depth_texture_;
    ComPtr<ID3D11DepthStencilView> dsv_;

    rtstarv::Mat4 view_;
    rtstarv::Mat4 projection_;
    int width_ = 0, height_ = 0;
};
