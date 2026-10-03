import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Library build of the components alone (the app build is vite.config.ts): ESM with React external,
// for the design-system sync. `npm run build:lib` also emits the .d.ts tree beside it.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist-lib",
    lib: { entry: "src/components/index.ts", formats: ["es"], fileName: "index" },
    rollupOptions: { external: ["react", "react-dom", "react/jsx-runtime"] },
    cssCodeSplit: false,
  },
});
