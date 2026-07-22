#pragma once

#include <cstdint>

namespace bionic_fg {

struct Config {
    uint32_t width = 0;
    uint32_t height = 0;
    uint32_t multiplier = 2;
    float flowScale = 0.6f;
    // model: 0 = model-0 hybrid OF chain, 1 = traced model-1 dispatch graph,
    //        2 = "V2 engine" — the model-1 graph rebuilt with libGameScopeV2.so
    //            shader variants substituted where a V2 variant exists
    //            (see embedded::kV2ShaderMap). model 2 is UNVERIFIED on device.
    //        3 = "FSR3 Optical Flow" — a color-only FidelityFX-SDK OF front-end
    //            (luma pyramid + SAD block flow) feeding the model-0 warp/blend +
    //            synthesis back half. UNVERIFIED on device.
    uint32_t model = 0;

    void sanitize() {
        if (multiplier < 2) multiplier = 0;
        if (multiplier > 4) multiplier = 4;
        if (flowScale < 0.2f) flowScale = 0.2f;
        if (flowScale > 1.0f) flowScale = 1.0f;
        if (model > 3) model = 3;
    }
};

} // namespace bionic_fg
