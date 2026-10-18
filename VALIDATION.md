# Editable frontend

The running app uses `ui/auth_studio/frontend/app.js`, a prepared browser bundle.
Source is in `ui/auth_studio/frontend/src/`. End users do not need Node.

For development, with Node 22+ installed:

```powershell
cd build_source
npm install
node build_frontend.mjs
```

Then restart Streamlit and hard-refresh the browser. The prepared assets are
local files, so the app makes no CDN requests to load Three.js or its models.

`camera.js` contains the original camera functions within a factory. The
included verification report concerns camera geometry only, not visual quality.

Each `.glb` in `frontend/assets/models` contains ordinary 3D geometry and embedded
textures. They can be imported into a 3D editor for further work. Textures use
WebP inside glTF's `EXT_texture_webp` extension. Individual leaves are contour
geometry rather than camera-facing tree photographs. Skin, fabric and foliage
use opaque/masked depth writes to avoid the legacy assets' transparent sorting
problems.

This constructed scene still falls short of the supplied photorealistic style
reference. Higher-quality scene production is needed to finish that requirement.
