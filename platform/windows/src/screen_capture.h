// platform/windows/src/screen_capture.h
#pragma once
#include <d3d11.h>
#include <dxgi1_2.h>
#include <wrl/client.h>
#include <vector>

using Microsoft::WRL::ComPtr;

class ScreenCapture {
public:
    bool init(ID3D11Device* device);
    void destroy();

    void acquire_frame(int display_index);
    ID3D11ShaderResourceView* get_texture(int display_index);
    int display_count() const { return static_cast<int>(outputs_.size()); }

private:
    struct OutputCapture {
        ComPtr<IDXGIOutputDuplication> duplication;
        ComPtr<ID3D11Texture2D> staging_texture;
        ComPtr<ID3D11ShaderResourceView> srv;
        bool has_frame = false;
    };

    ID3D11Device* device_ = nullptr;
    std::vector<OutputCapture> outputs_;
};
