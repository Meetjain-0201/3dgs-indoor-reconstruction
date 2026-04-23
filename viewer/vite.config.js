import { defineConfig } from 'vite';
import { resolve } from 'node:path';

// Multi-page build: index.html is the scene picker, viewer.html is the
// canvas host. Without this, vite build only emits the root index.
export default defineConfig({
  build: {
    rollupOptions: {
      input: {
        index: resolve(import.meta.dirname, 'index.html'),
        viewer: resolve(import.meta.dirname, 'viewer.html'),
      },
    },
  },
});
