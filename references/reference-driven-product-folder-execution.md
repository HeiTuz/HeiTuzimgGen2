# Reference-driven apparel product folders

Use this when a source folder contains product images plus filename cues such as `f1`, `b1`, `cN`, `dN`, or Korean instructions like `상품택제거`.

## Evidence order

1. **Vision observation overrides shorthand role assumptions.** Treat filenames as shot intent, not proof that a `cN` image is front-facing. If the image visibly shows a back panel, preserve that back panel.
2. Build an immutable `ProductSpec` before generation: silhouette, relative dimensions, neck/strap geometry, seams, closure hardware, fabric texture, and only the colourways actually observed.
3. Compile that spec into every per-cut prompt. Do not let a generic "product correction" prompt replace observable construction.

## Filename directives

- `상품택제거`: remove only a temporary loose swing/hang tag. Retain sewn-in labels when they are part of the garment construction unless the filename explicitly says otherwise.
- `앞면후크잠금컷`: make a true detail crop of the observed hook-and-eye/placket mechanics; do not substitute a generic full-garment image.
- For multi-colour sets, one output carries one observed colourway. Cover all observed colourways before repeating one; do not invent colours.

## Per-cut contract

Preserve the exact source-supported view and product geometry, even if it disagrees with a filename-derived default role. Apply the user-specified lighting/background consistently. Keep each generated cut isolated: no model, hanger, hands, props, or collage unless supplied as intentional product evidence.

## QC minimums

Review each final cut against the target source for: product view/role, silhouette and seam placement, closure construction, colourway, temporary-tag removal, and background. Reject a cut that introduces a loose tag, swaps a front/back view, or converts a requested detail cut into a full product view.
