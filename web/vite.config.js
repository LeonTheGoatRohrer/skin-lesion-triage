import { defineConfig } from 'vite';
import tailwindcss from '@tailwindcss/vite';

// Relativer base-Pfad: Die gebaute App läuft aus jedem Unterordner (z. B. GitHub Pages).
export default defineConfig({
  base: './',
  plugins: [tailwindcss()],
  build: {
    target: 'es2020',
    chunkSizeWarningLimit: 1500,
  },
  optimizeDeps: {
    exclude: ['onnxruntime-web'],
  },
});
