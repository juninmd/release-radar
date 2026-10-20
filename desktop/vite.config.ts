import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// Tauri espera a porta fixa 1420 no dev; o alvo esnext combina com o WebView2 moderno.
// Fora do Tauri (bun run dev no navegador), VITE_API_BASE habilita um proxy para a API do servidor.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const target = env.VITE_API_BASE;
  return {
    plugins: [react()],
    clearScreen: false,
    server: {
      port: 1420,
      strictPort: true,
      watch: { ignored: ["**/src-tauri/**"] },
      proxy: target
        ? { "/api": { target, changeOrigin: true, secure: true } }
        : undefined,
    },
    build: { target: "esnext" },
  };
});
