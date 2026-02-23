import {
  defineConfig,
  minimal2023Preset,
} from '@vite-pwa/assets-generator/config';

export default defineConfig({
  preset: {
    ...minimal2023Preset,
    transparent: {
      ...minimal2023Preset.transparent!,
      padding: 0,
      resizeOptions: { fit: 'cover' },
    },
    maskable: { sizes: [] },
    apple: {
      ...minimal2023Preset.apple!,
      padding: 0,
      resizeOptions: { fit: 'cover' },
    },
  },
  images: ['public/btaa-geoportal-logo.png'],
});
