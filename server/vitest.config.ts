import { defineConfig } from "vitest/config";
import { resolve } from "node:path";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    // PGlite boots a Postgres wasm build per suite. The 5s default is not enough
    // when the machine is busy, and the timeout reads like a broken test rather
    // than load, which costs a debugging detour every time.
    testTimeout: 60000,
    hookTimeout: 60000,
  },
  resolve: { alias: { "@": resolve(__dirname, ".") } },
});
