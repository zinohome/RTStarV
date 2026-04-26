// platform/windows/src/screen_capture.cpp
#include "screen_capture.h"

bool ScreenCapture::init(ID3D11Device* device) {
    device_ = device;

    ComPtr<IDXGIDevice> dxgi_device;
    device->QueryInterface(IID_PPV_ARGS(&dxgi_device));

    ComPtr<IDXGIAdapter> adapter;
    dxgi_device->GetAdapter(&adapter);

    ComPtr<IDXGIOutput> output;
    for (UINT i = 0; adapter->EnumOutputs(i, &output) != DXGI_ERROR_NOT_FOUND; i++) {
        ComPtr<IDXGIOutput1> output1;
        output.As(&output1);

        OutputCapture oc;
        HRESULT hr = output1->DuplicateOutput(device, &oc.duplication);
        if (SUCCEEDED(hr)) {
            DXGI_OUTDUPL_DESC desc;
            oc.duplication->GetDesc(&desc);

            D3D11_TEXTURE2D_DESC td = {};
            td.Width = desc.ModeDesc.Width;
            td.Height = desc.ModeDesc.Height;
            td.MipLevels = 1;
            td.ArraySize = 1;
            td.Format = desc.ModeDesc.Format;
            td.SampleDesc.Count = 1;
            td.Usage = D3D11_USAGE_DEFAULT;
            td.BindFlags = D3D11_BIND_SHADER_RESOURCE;
            device->CreateTexture2D(&td, nullptr, &oc.staging_texture);

            D3D11_SHADER_RESOURCE_VIEW_DESC srvd = {};
            srvd.Format = td.Format;
            srvd.ViewDimension = D3D11_SRV_DIMENSION_TEXTURE2D;
            srvd.Texture2D.MipLevels = 1;
            device->CreateShaderResourceView(oc.staging_texture.Get(), &srvd, &oc.srv);

            outputs_.push_back(std::move(oc));
        }
        output.Reset();
    }

    return !outputs_.empty();
}

void ScreenCapture::acquire_frame(int display_index) {
    if (display_index < 0 || display_index >= static_cast<int>(outputs_.size())) return;

    auto& oc = outputs_[display_index];
    if (!oc.duplication) return;

    ComPtr<IDXGIResource> resource;
    DXGI_OUTDUPL_FRAME_INFO info;
    HRESULT hr = oc.duplication->AcquireNextFrame(0, &info, &resource);

    if (hr == DXGI_ERROR_WAIT_TIMEOUT) return;

    if (hr == DXGI_ERROR_ACCESS_LOST) {
        oc.duplication.Reset();
        return;
    }

    if (SUCCEEDED(hr)) {
        ComPtr<ID3D11Texture2D> frame_tex;
        resource.As(&frame_tex);

        ComPtr<ID3D11DeviceContext> ctx;
        device_->GetImmediateContext(&ctx);
        ctx->CopyResource(oc.staging_texture.Get(), frame_tex.Get());

        oc.duplication->ReleaseFrame();
        oc.has_frame = true;
    }
}

ID3D11ShaderResourceView* ScreenCapture::get_texture(int display_index) {
    if (display_index < 0 || display_index >= static_cast<int>(outputs_.size())) return nullptr;
    acquire_frame(display_index);
    return outputs_[display_index].srv.Get();
}

void ScreenCapture::destroy() {
    for (auto& oc : outputs_) {
        if (oc.duplication) {
            oc.duplication->ReleaseFrame();
            oc.duplication.Reset();
        }
    }
    outputs_.clear();
}
