import fs from "fs";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  if (!fs.existsSync(".env.local")) {
    throw new Error(
      "Missing frontend/.env.local — create it with your Cognito and API key values.\n" +
        "See the 'Local development' section in the README for the required variables.",
    );
  }

  const env = loadEnv(mode, process.cwd());

  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: {
        "/api": {
          target: "https://api.doubleday-dev.appleforge.com",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
          headers: {
            "x-api-key": env.VITE_API_KEY || "",
          },
        },
      },
    },
  };
});
