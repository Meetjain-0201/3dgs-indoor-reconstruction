import * as THREE from 'three';
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

// Redirect back to the scene picker if no scene was specified.
const params = new URLSearchParams(window.location.search);
const scene = params.get('scene');
if (!scene) {
  window.location.replace('index.html');
  throw new Error('no scene param; redirecting to index');
}

// HUD: scene label
document.getElementById('scene-name').textContent = scene;
document.title = `3dgs viewer: ${scene}`;

// Progress bar wiring
const loadingEl = document.getElementById('loading');
const loadingFill = document.getElementById('loading-fill');
const loadingText = document.getElementById('loading-text');

function setProgress(percent) {
  const clamped = Math.max(0, Math.min(100, percent));
  loadingFill.style.width = `${clamped}%`;
  loadingText.textContent = `loading... ${clamped.toFixed(0)}%`;
}

function hideLoading() {
  loadingEl.classList.add('hidden');
}

function failLoading(message) {
  loadingFill.style.background = '#5a1f2a';
  loadingText.textContent = message;
}

// --- viewer setup ---
const rootElement = document.getElementById('canvas-root');

const viewer = new GaussianSplats3D.Viewer({
  rootElement,
  useBuiltInControls: true,
  selfDrivenMode: true,
  sharedMemoryForWorkers: false,
  gpuAcceleratedSort: true,
  ignoreDevicePixelRatio: false,
});

// Force the WebGL clear color to our dark theme. The Viewer creates its own
// renderer; we just override the clear color after construction.
function applyClearColor() {
  const renderer = viewer.renderer;
  if (renderer && typeof renderer.setClearColor === 'function') {
    renderer.setClearColor(new THREE.Color(0x0a0a0f), 1);
  }
}
applyClearColor();

// --- load the splat scene ---
const splatUrl = `${encodeURIComponent(scene)}.ksplat`;

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
    viewer.start();
    applyClearColor();
  })
  .catch((err) => {
    console.error('failed to load splat scene', err);
    failLoading(`failed to load ${splatUrl} (see console)`);
  });

// --- FPS counter, averaged over a 500ms window ---
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
