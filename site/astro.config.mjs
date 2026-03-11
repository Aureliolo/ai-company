import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

export default defineConfig({
  integrations: [tailwind()],
  site: "https://synthorg.io",
  // Docs live at /docs (served by MkDocs build output merged in CI)
  // Landing page is everything else
  build: {
    assets: "_assets",
  },
});
