# Browser-backed image editing

Use this lane when the user explicitly prefers an in-app or authenticated browser workflow instead of the default CLI transport.

## Contract

1. **Honor the requested surface.** Keep generation inside the named browser/app unless that route is genuinely blocked. Do not silently substitute a native provider or CLI route.
2. **Materialize the source first.** For protected CDN URLs that return `403` to `curl` or server-side vision, navigate to the exact image URL in the user's authenticated browser. If the browser renders the image, save/download it and verify the local artifact with file type, pixel dimensions, and hash before editing.
3. **Treat attachment as a state transition, not a click.** After upload/paste/file-picker interaction, verify the composer actually contains an attachment using at least one of:
   - visible preview thumbnail in a fresh screenshot;
   - attachment/remove control in the accessibility tree or DOM;
   - file count/name in the active input when the browser exposes it.
   A send button or successful paste keystroke alone is not attachment evidence.
4. **Do not submit the generation prompt until attachment verification passes.** If the model replies that no image is attached, stop prompt retries and repair the upload path.
5. **Prefer independent edits from the same original for staged transformations.** For progressive face/casting changes, upload/reference the original for each stage rather than feeding stage N into stage N+1. This limits identity, texture, and composition drift.
6. **Keep invariants explicit.** Lock crop, camera, pose, hair, background, lighting, skin texture, marks/asymmetry, and editorial grade separately from the facial attributes that intentionally change.

## macOS upload recovery ladder

Use the narrowest successful method and verify after each rung:

1. Native file-input click or visible **Add files** control, then choose the verified local source.
2. Real clipboard image paste into a focused composer. Set an actual PNG/TIFF/JPEG image flavor, not a text path; then verify a thumbnail/control appeared.
3. Finder drag-and-drop into the visible composer when supported.
4. Browser-specific remote-debugging/CDP upload (`DOM.setFileInputFiles`) only when the user's existing authenticated browser profile exposes an approved debugging surface.
5. If macOS blocks scripted keystrokes or Accessibility control, report the exact one-time user action needed (grant permission or manually attach the already-prepared file). Keep the browser, prompt, and verified source ready so the user performs only that irreducible step.

Do not encode a transient permission denial as “browser upload does not work.” The durable lesson is to verify attachment state and move down the recovery ladder.

## Protected CDN source recovery

A CDN `403` from command-line fetch does not prove the image is unavailable. Try the user's authenticated browser before giving up. Once rendered, prefer a browser download/save that preserves the original bytes; verify dimensions and hash locally. Screenshots are inspection evidence only and should not replace the original editing source unless the user accepts that loss.
