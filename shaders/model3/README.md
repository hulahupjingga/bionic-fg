# model 3 — FSR3 Optical Flow shaders

GLSL compute source-of-truth for bionic-fg **model 3** (color-only FSR3 Optical
Flow front-end). These are subgroup-free / SPD-free adaptations of the AMD
FidelityFX-SDK FSR3 Optical Flow passes — see `NOTICE_FIDELITYFX_OPTICALFLOW.md`
(MIT) and the per-file DEVIATION comments. They feed the model-0 warp/blend +
synthesis back half via `flowExpA_`/`flowExpB_`.

| file                 | role             | embedded idx | bindings (set 0)                         | storage fmt |
|----------------------|------------------|--------------|------------------------------------------|-------------|
| `of3_luma.comp`      | Rec.709 luma     | 66           | 32 src color, 48 dst                      | r32f        |
| `of3_downsample.comp`| box mip reduce   | 67           | 32 src level, 48 dst level                | r32f        |
| `of3_flow.comp`      | SAD block flow   | 68           | 0 ubo, 32 prevLuma, 33 currLuma, 34 pred, 48 flow | rgba16f |
| `of3_expand.comp`    | scale + fwd/bwd  | 69           | 0 ubo, 32 flowFine, 48 fwd, 49 bwd        | rgba16f     |

Flow vectors are carried in **full-resolution pixel units** at every pyramid
level so the coarse→fine predictor needs no rescale.

## Regenerate the embedded SPIR-V

```sh
# 1) compile (Vulkan 1.1 / SPIR-V 1.3, Adreno/Turnip-safe; caps = Shader, ImageQuery)
for s in of3_luma of3_downsample of3_flow of3_expand; do
  glslangValidator -e main -S comp --target-env vulkan1.1 -V shaders/model3/$s.comp -o $s.spv
done
# 2) convert to the shaders_embedded.hpp byte-array form
python3 <scratch>/spv_to_carray.py arrays.inc \
  of3_luma.spv shader_66_data  of3_downsample.spv shader_67_data \
  of3_flow.spv shader_68_data  of3_expand.spv shader_69_data
# 3) paste shader_66_data..shader_69_data into src/shaders_embedded.hpp (idx 66-69)
```

## Device tuning knobs
`of3_flow.comp`: `BR` (block half-window) and `SR` (per-level search radius) are
reduced from the SDK's 8×8 / ±8 to 3×3 / ±3 for non-subgroup GLSL on Turnip.
Raise for quality, lower for speed. No sub-pixel refinement yet.
