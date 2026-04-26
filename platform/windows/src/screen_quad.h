// platform/windows/src/screen_quad.h
#pragma once
#include "d3d11_renderer.h"
#include <d3d11.h>
#include <wrl/client.h>

using Microsoft::WRL::ComPtr;

struct ScreenQuad {
    ScreenTransform transform;
    ComPtr<ID3D11Texture2D> texture;
    ComPtr<ID3D11ShaderResourceView> srv;
    int display_index = -1;
};
