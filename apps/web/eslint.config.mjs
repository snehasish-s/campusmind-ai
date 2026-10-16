import { defineConfig, globalIgnores } from "eslint/config";
import js from "@eslint/js";
import tseslint from "typescript-eslint";
import hooks from "eslint-plugin-react-hooks";
export default defineConfig([
  globalIgnores([".next/**", "next-env.d.ts", "test-results/**"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    plugins: { "react-hooks": hooks },
    rules: { ...hooks.configs.recommended.rules },
  },
]);
