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
| `of3_flow_m4.comp`   | **model 4** flow | 70           | as 68 (flow packs .xy fwd, .zw bwd)       | rgba16f     |
| `of3_expand_m4.comp` | **model 4** expand | 71         | as 69, plus occlusion gating              | rgba16f     |

Flow vectors are carried in **full-resolution pixel units** at every pyramid
level so the coarse→fine predictor needs no rescale.

## Model 4 — "FSR3 Optical Flow v2"

Model 4 is a **separate selectable model**, not a replacement: model 3 is left
bit-identical so the two can be A/B'd live on the same scene. It reuses model
3's luma (66) and downsample (67) passes unchanged and differs only in the flow
search and the expand pass. Four changes:

1. **Block grid.** One invocation solves one `kBlock`×`kBlock` block (`kBlock`
   = 4, in `framegen_context.cpp`), as the SDK does, instead of one per pixel.
   Flow images are `1/kBlock` of each level's extent; every consumer samples
   flow by normalised uv, so the coarser grid bilinear-upsamples for free. This
   removes 16× the invocations and is what pays for the rest. Model 3 sets
   `kBlock = 1`, which makes `blockExtent == levelExtent` — that is how model 3
   stays exactly as it was.
2. **Match window 3×3 → 5×5** (`BR` 1 → 2). A 3×3 window is badly aperture-
   limited and locks onto the wrong candidate on low-contrast or edge-dominated
   blocks. Main accuracy fix.
3. **Sub-pixel refinement** — parabola fit through the SAD either side of the
   integer winner, per axis. Without it slow pans quantise to whole texels and
   the generated frame judders.
4. **True bidirectional flow.** Forward is packed in `.xy`, an independently
   searched backward field in `.zw`. `of3_expand_m4` gates on their
   disagreement: where the two fail to cancel, something was occluded or
   revealed (or the scene cut), so flow is attenuated toward zero and the
   downstream warp/blend degrades to a cross-fade instead of warping along a
   wrong vector. This is also why model 4 needs no scene-change pass.

Net search cost is ~2.7× **lower** than model 3's per-pixel version despite
searching both directions with a 25-tap window.

Coarse-to-fine reach over 5 levels is ±`SR`·(1+2+4+8+16) = ±93 full-res pixels,
so keeping `SR` at ±3 costs no motion range.

## Regenerate the embedded SPIR-V

```sh
# 1) compile (Vulkan 1.1 / SPIR-V 1.3, Adreno/Turnip-safe; caps = Shader, ImageQuery)
for s in of3_luma of3_downsample of3_flow of3_expand of3_flow_m4 of3_expand_m4; do
  glslangValidator -e main -S comp --target-env vulkan1.1 -V shaders/model3/$s.comp -o $s.spv
done
# 2) splice into src/shaders_embedded.hpp in place, preserving the byte-array format
python3 tools/splice_spv.py src/shaders_embedded.hpp \
  66=of3_luma.spv 67=of3_downsample.spv 68=of3_flow.spv 69=of3_expand.spv \
  70=of3_flow_m4.spv 71=of3_expand_m4.spv
```

All six must recompile byte-identical against what is embedded — a useful check
that the toolchain matches before changing anything.

## Device tuning knobs
- `of3_flow.comp` / `of3_flow_m4.comp`: `BR` (block half-window) and `SR`
  (search radius). Raise for quality, lower for speed. Model 3's are still the
  SDK's 8×8 / ±8 reduced to 3×3 / ±3.
- `framegen_context.cpp`: `kBlock` — model 4's flow density vs cost. 8 matches
  the SDK, but FSR3 leans on game motion vectors for fine detail, which a
  colour-only layer has none of; 4 keeps the field dense enough to stand alone.
- `framegen_context.hpp`: `kModel3OcclLo` / `kModel3OcclHi` — how readily model
  4 suppresses flow on forward/backward disagreement. Lower = more cross-fade,
  safer; higher = more warping, sharper but riskier at occlusion edges.
