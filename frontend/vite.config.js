import { defineConfig } from 'vite'
import preact from '@preact/preset-vite'

export default defineConfig({
  plugins: [preact()],
  build: {
    outDir: '../custom_components/rbac/www',
    rollupOptions: {
      input: 'src/index.html',
      output: {
        entryFileNames: 'config.js',
        chunkFileNames: '[name].js',
        assetFileNames: (assetInfo) => {
          if (assetInfo.name === 'index.html') {
            return 'config.html'
          }
          return '[name].[ext]'
        }
      }
    }
  },
  base: '/api/rbac/static/'
})
