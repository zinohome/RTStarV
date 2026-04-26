// platform/windows/src/d3d11_renderer.cpp
#include "d3d11_renderer.h"
#include <d3dcompiler.h>
#include <cstring>

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "d3dcompiler.lib")

struct Vertex {
    float pos[3];
    float uv[2];
};

struct CBData {
    rtstarv::Mat4 mvp;
    float border[4]; // r, g, b, width
};

bool D3D11Renderer::init(HWND hwnd, int width, int height) {
    width_ = width;
    height_ = height;

    DXGI_SWAP_CHAIN_DESC1 scd = {};
    scd.Width = width;
    scd.Height = height;
    scd.Format = DXGI_FORMAT_B8G8R8A8_UNORM;
    scd.SampleDesc.Count = 1;
    scd.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    scd.BufferCount = 2;
    scd.SwapEffect = DXGI_SWAP_EFFECT_FLIP_DISCARD;

    D3D_FEATURE_LEVEL featureLevel = D3D_FEATURE_LEVEL_11_0;
    UINT flags = 0;
#ifdef _DEBUG
    flags |= D3D11_CREATE_DEVICE_DEBUG;
#endif

    ComPtr<IDXGIFactory2> factory;
    if (FAILED(CreateDXGIFactory1(IID_PPV_ARGS(&factory)))) return false;

    if (FAILED(D3D11CreateDevice(nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, flags,
                      &featureLevel, 1, D3D11_SDK_VERSION,
                      &device_, nullptr, &context_))) return false;

    if (FAILED(factory->CreateSwapChainForHwnd(device_.Get(), hwnd, &scd, nullptr, nullptr, &swap_chain_))) return false;

    ComPtr<ID3D11Texture2D> backbuffer;
    if (FAILED(swap_chain_->GetBuffer(0, IID_PPV_ARGS(&backbuffer)))) return false;
    if (FAILED(device_->CreateRenderTargetView(backbuffer.Get(), nullptr, &rtv_))) return false;

    // depth buffer for correct multi-screen occlusion
    D3D11_TEXTURE2D_DESC dtd = {};
    dtd.Width = width;
    dtd.Height = height;
    dtd.MipLevels = 1;
    dtd.ArraySize = 1;
    dtd.Format = DXGI_FORMAT_D24_UNORM_S8_UINT;
    dtd.SampleDesc.Count = 1;
    dtd.Usage = D3D11_USAGE_DEFAULT;
    dtd.BindFlags = D3D11_BIND_DEPTH_STENCIL;
    if (FAILED(device_->CreateTexture2D(&dtd, nullptr, &depth_texture_))) return false;
    if (FAILED(device_->CreateDepthStencilView(depth_texture_.Get(), nullptr, &dsv_))) return false;

    D3D11_VIEWPORT vp = {0, 0, (float)width, (float)height, 0, 1};
    context_->RSSetViewports(1, &vp);

    projection_ = rtstarv::mat4_perspective(43.5f, (float)width / height, 0.1f, 100.0f);

    if (!create_shaders()) return false;
    if (!create_quad_geometry()) return false;

    D3D11_SAMPLER_DESC sd = {};
    sd.Filter = D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sd.AddressU = sd.AddressV = sd.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP;
    if (FAILED(device_->CreateSamplerState(&sd, &sampler_))) return false;

    D3D11_BUFFER_DESC cbd = {};
    cbd.ByteWidth = sizeof(CBData);
    cbd.Usage = D3D11_USAGE_DYNAMIC;
    cbd.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
    cbd.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE;
    if (FAILED(device_->CreateBuffer(&cbd, nullptr, &constant_buffer_))) return false;

    return true;
}

bool D3D11Renderer::create_shaders() {
    const char vs_src[] = R"(
        cbuffer CB : register(b0) { float4x4 mvp; float4 border_color; };
        struct VS { float3 pos : POSITION; float2 uv : TEXCOORD0; };
        struct PS { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };
        PS main(VS i) { PS o; o.pos = mul(mvp, float4(i.pos, 1.0)); o.uv = i.uv; return o; }
    )";

    const char ps_src[] = R"(
        cbuffer CB : register(b0) { float4x4 mvp; float4 border_color; };
        Texture2D tex : register(t0);
        SamplerState samp : register(s0);
        struct PS { float4 pos : SV_POSITION; float2 uv : TEXCOORD0; };
        float4 main(PS i) : SV_TARGET {
            float2 uv = i.uv; float bw = border_color.w;
            if (bw > 0.0 && (uv.x < bw || uv.x > 1.0 - bw || uv.y < bw || uv.y > 1.0 - bw))
                return float4(border_color.rgb, 1.0);
            return tex.Sample(samp, uv);
        }
    )";

    ComPtr<ID3DBlob> vs_blob, ps_blob, err;
    HRESULT hr = D3DCompile(vs_src, sizeof(vs_src), "vs", nullptr, nullptr, "main", "vs_5_0", 0, 0, &vs_blob, &err);
    if (FAILED(hr)) return false;

    hr = D3DCompile(ps_src, sizeof(ps_src), "ps", nullptr, nullptr, "main", "ps_5_0", 0, 0, &ps_blob, &err);
    if (FAILED(hr)) return false;

    device_->CreateVertexShader(vs_blob->GetBufferPointer(), vs_blob->GetBufferSize(), nullptr, &vs_);
    device_->CreatePixelShader(ps_blob->GetBufferPointer(), ps_blob->GetBufferSize(), nullptr, &ps_);

    D3D11_INPUT_ELEMENT_DESC layout[] = {
        {"POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D11_INPUT_PER_VERTEX_DATA, 0},
        {"TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT, 0, 12, D3D11_INPUT_PER_VERTEX_DATA, 0},
    };
    device_->CreateInputLayout(layout, 2, vs_blob->GetBufferPointer(), vs_blob->GetBufferSize(), &input_layout_);

    return true;
}

bool D3D11Renderer::create_quad_geometry() {
    Vertex verts[] = {
        {{-0.5f, -0.5f, 0}, {0, 1}},
        {{-0.5f,  0.5f, 0}, {0, 0}},
        {{ 0.5f,  0.5f, 0}, {1, 0}},
        {{ 0.5f, -0.5f, 0}, {1, 1}},
    };
    UINT indices[] = {0, 1, 2, 0, 2, 3};

    D3D11_BUFFER_DESC vbd = {};
    vbd.ByteWidth = sizeof(verts);
    vbd.Usage = D3D11_USAGE_IMMUTABLE;
    vbd.BindFlags = D3D11_BIND_VERTEX_BUFFER;
    D3D11_SUBRESOURCE_DATA vsd = {verts};
    device_->CreateBuffer(&vbd, &vsd, &vertex_buffer_);

    D3D11_BUFFER_DESC ibd = {};
    ibd.ByteWidth = sizeof(indices);
    ibd.Usage = D3D11_USAGE_IMMUTABLE;
    ibd.BindFlags = D3D11_BIND_INDEX_BUFFER;
    D3D11_SUBRESOURCE_DATA isd = {indices};
    device_->CreateBuffer(&ibd, &isd, &index_buffer_);

    return true;
}

void D3D11Renderer::begin_frame(float r, float g, float b, float a) {
    float color[] = {r, g, b, a};
    context_->OMSetRenderTargets(1, rtv_.GetAddressOf(), dsv_.Get());
    context_->ClearRenderTargetView(rtv_.Get(), color);
    context_->ClearDepthStencilView(dsv_.Get(), D3D11_CLEAR_DEPTH, 1.0f, 0);
}

void D3D11Renderer::set_camera(float yaw_deg, float pitch_deg, float roll_deg) {
    using namespace rtstarv;
    auto ry = mat4_rotation_y(-yaw_deg * DEG2RAD);
    auto rx = mat4_rotation_x(pitch_deg * DEG2RAD);
    auto rz = mat4_rotation_z(roll_deg * DEG2RAD);
    view_ = mat4_multiply(rz, mat4_multiply(rx, ry));
}

void D3D11Renderer::draw_screen_quad(const ScreenTransform& screen, ID3D11ShaderResourceView* texture, bool focused) {
    using namespace rtstarv;

    auto scale = Mat4{screen.width,0,0,0, 0,screen.height,0,0, 0,0,1,0, 0,0,0,1};
    auto rot_y = mat4_rotation_y(screen.yaw_deg * DEG2RAD);
    auto rot_x = mat4_rotation_x(-screen.pitch_deg * DEG2RAD);
    auto trans = mat4_translation(screen.position.x, screen.position.y, screen.position.z);

    auto model = mat4_multiply(trans, mat4_multiply(rot_y, mat4_multiply(rot_x, scale)));
    auto mvp = mat4_multiply(projection_, mat4_multiply(view_, model));

    CBData cb;
    cb.mvp = mvp;
    cb.border[0] = 1.0f; cb.border[1] = 1.0f; cb.border[2] = 1.0f;
    cb.border[3] = focused ? 0.005f : 0.0f;

    D3D11_MAPPED_SUBRESOURCE mapped;
    context_->Map(constant_buffer_.Get(), 0, D3D11_MAP_WRITE_DISCARD, 0, &mapped);
    memcpy(mapped.pData, &cb, sizeof(cb));
    context_->Unmap(constant_buffer_.Get(), 0);

    context_->IASetInputLayout(input_layout_.Get());
    UINT stride = sizeof(Vertex), offset = 0;
    context_->IASetVertexBuffers(0, 1, vertex_buffer_.GetAddressOf(), &stride, &offset);
    context_->IASetIndexBuffer(index_buffer_.Get(), DXGI_FORMAT_R32_UINT, 0);
    context_->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);

    context_->VSSetShader(vs_.Get(), nullptr, 0);
    context_->VSSetConstantBuffers(0, 1, constant_buffer_.GetAddressOf());
    context_->PSSetShader(ps_.Get(), nullptr, 0);
    context_->PSSetConstantBuffers(0, 1, constant_buffer_.GetAddressOf());
    context_->PSSetSamplers(0, 1, sampler_.GetAddressOf());

    if (texture) {
        context_->PSSetShaderResources(0, 1, &texture);
    } else {
        ID3D11ShaderResourceView* null_srv = nullptr;
        context_->PSSetShaderResources(0, 1, &null_srv);
    }

    context_->DrawIndexed(6, 0, 0);
}

void D3D11Renderer::end_frame() {
    swap_chain_->Present(0, 0);
}

void D3D11Renderer::destroy() {
    if (context_) context_->ClearState();
}
