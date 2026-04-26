// platform/windows/shaders/screen_vs.hlsl
cbuffer Constants : register(b0) {
    float4x4 mvp;
    float4 border_color; // (r, g, b, border_width)
};

struct VSInput {
    float3 pos : POSITION;
    float2 uv  : TEXCOORD0;
};

struct PSInput {
    float4 pos : SV_POSITION;
    float2 uv  : TEXCOORD0;
};

PSInput main(VSInput input) {
    PSInput output;
    output.pos = mul(mvp, float4(input.pos, 1.0));
    output.uv = input.uv;
    return output;
}
