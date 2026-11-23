import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["node_modules/**", "*.min.js", "vendor/**"] },
  js.configs.recommended,
  {
    files: ["*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: {
        ...globals.browser,
        ...globals.jquery,
        ...globals.node,
      },
    },
  },
  { files: ["notifications-center-api-integration.js", "notifications-websocket-integration.js"], languageOptions: { globals: { NotificationsCenter: "readonly" } } },
  { files: ["env_manager.js"], languageOptions: { globals: { DEPLOYMENT_ID: "readonly", CSRF_TOKEN: "readonly" } } },
];
