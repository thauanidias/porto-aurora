import {defineConfig} from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
export default defineConfig({plugins:[react(),tailwindcss()],build:{rollupOptions:{output:{assetFileNames: asset => asset.names.some(name => name.endsWith('.mjs')) ? 'assets/[name]-[hash].js' : 'assets/[name]-[hash][extname]'}}},server:{proxy:{'/api':'http://localhost:8088'}},test:{environment:'jsdom',include:['src/**/*.test.tsx','src/**/*.test.ts']}});
