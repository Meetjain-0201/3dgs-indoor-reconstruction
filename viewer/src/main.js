import * as THREE from 'three';
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

// Redirect back to the scene picker if no scene was specified.
const params = new URLSearchParams(window.location.search);
const scene = params.get('scene');
if (!scene) {
  window.location.replace('index.html');
  throw new Error('no scene param; redirecting to index');
}

// HUD: scene label + title
document.getElementById('scene-name').textContent = scene;
document.title = `3dgs viewer: ${scene}`;

// Loading bar wiring
const loadingEl = document.getElementById('loading');
const loadingFill = document.getElementById('loading-fill');
const loadingText = document.getElementById('loading-text');

function setProgress(percent) {
  const clamped = Math.max(0, Math.min(100, percent));
  loadingFill.style.width = `${clamped}%`;
  loadingText.textContent = `loading... ${clamped.toFixed(0)}%`;
}
function hideLoading() { loadingEl.classList.add('hidden'); }
function failLoading(msg) {
  loadingFill.style.background = '#5a1f2a';
  loadingText.textContent = msg;
}

const rootElement = document.getElementById('canvas-root');

// Notes on the Viewer options:
//   cameraUp [0,-1,0]:       COLMAP world has +Y pointing down (gravity), so
//                            up is -Y. Without this the scene renders upside
//                            down relative to the built-in orbit controls.
//   gpuAcceleratedSort false: with this true, the sort worker never gets the
//                            splat centers (they're expected on the GPU) and
//                            uploadedSplatCount stays 0, leaving drawRange at
//                            0 and the canvas black. CPU sort is fine for
//                            scenes in the hundreds-of-thousands range.
//   sceneRevealMode Instant: default Default mode fades splats in based on
//                            firstRenderTime, which only advances once at
//                            least one splat has been rendered. Instant skips
//                            that gate.
const viewer = new GaussianSplats3D.Viewer({
  rootElement,
  useBuiltInControls: true,
  selfDrivenMode: true,
  sharedMemoryForWorkers: false,
  gpuAcceleratedSort: false,
  ignoreDevicePixelRatio: false,
  cameraUp: [0, -1, 0],
  initialCameraPosition: [2.608, 0.328, -1.376],
  initialCameraLookAt: [-0.188, -1.08, 2.523],
  sceneRevealMode: GaussianSplats3D.SceneRevealMode.Instant,
});

// Expose for devtools poking.
window.viewer = viewer;
window.THREE = THREE;

// Override the WebGL clear color to match the dark theme.
if (viewer.renderer && typeof viewer.renderer.setClearColor === 'function') {
  viewer.renderer.setClearColor(new THREE.Color(0x0a0a0f), 1);
}

const splatUrl = `/${encodeURIComponent(scene)}.ksplat`;

viewer
  .addSplatScene(splatUrl, {
    showLoadingUI: false,
    progressiveLoad: false,
    onProgress: (percent) => {
      if (typeof percent === 'number') setProgress(percent);
    },
  })
  .then(() => {
    setProgress(100);
    hideLoading();
    // Force the camera matrix world to flush before start(). The first sort
    // reads camera.matrixWorld for frustum culling; if it's stale, every
    // splat lands outside the frustum.
    viewer.camera.updateMatrixWorld(true);
    viewer.splatMesh.updateMatrixWorld(true);
    viewer.start();
  })
  .catch((err) => {
    console.error('failed to load splat scene', err);
    failLoading(`failed to load ${splatUrl} (see console)`);
  });

// Top-right FPS HUD, averaged over a 500 ms window.
const fpsValue = document.getElementById('fps-value');
let frameCount = 0;
let windowStart = performance.now();

function rafTick() {
  frameCount++;
  requestAnimationFrame(rafTick);
}
requestAnimationFrame(rafTick);

setInterval(() => {
  const now = performance.now();
  const seconds = (now - windowStart) / 1000;
  const fps = seconds > 0 ? frameCount / seconds : 0;
  fpsValue.textContent = fps.toFixed(0);
  frameCount = 0;
  windowStart = now;
}, 500);
