import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  vite: {
    plugins: [tailwindcss()],
  },
  site: "https://synthorg.io",
  integrations: [sitemap()],
  // Docs live at /docs (served by Zensical build output merged in CI)
  // Landing page is everything else
  build: {
    assets: "_assets",
  },
});
