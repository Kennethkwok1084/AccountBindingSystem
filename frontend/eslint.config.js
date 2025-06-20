import js from "@eslint/js";
import vue from "eslint-plugin-vue";

export default [
  js.configs.recommended,
  ...vue.configs["flat/recommended"],
  {
    files: ["**/*.vue", "**/*.js"],
    languageOptions: {
      globals: {
        fetch: "readonly",
        URLSearchParams: "readonly",
        FormData: "readonly",
        Blob: "readonly",
        window: "readonly",
      },
    },
    plugins: { vue },
    rules: {
      "vue/no-multiple-template-root": "off",
    },
  },
];
