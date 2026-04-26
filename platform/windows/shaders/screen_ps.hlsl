// platform/windows/shaders/screen_ps.hlsl
cbuffer Constants : register(b0) {
    float4x4 mvp;
    float4 border_color; // (r, g, b, border_width)
};

Texture2D screenTex : register(t0);
SamplerState samp : register(s0);

struct PSInput {
    float4 pos : SV_POSITION;
    float2 uv  : TEXCOORD0;
};

float4 main(PSInput input) : SV_TARGET {
    float2 uv = input.uv;
    float bw = border_color.w;

    // 焦点屏幕白色边框
    if (bw > 0.0 && (uv.x < bw || uv.x > 1.0 - bw || uv.y < bw || uv.y > 1.0 - bw))
        return float4(border_color.rgb, 1.0);

    return screenTex.Sample(samp, uv);
}
