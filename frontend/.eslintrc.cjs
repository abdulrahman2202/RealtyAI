const nextPlugin = require("@next/eslint-plugin-next");

module.exports = {
  root: true,
  plugins: ["@next/next"],
  rules: {
    ...nextPlugin.configs.recommended.rules,
    ...nextPlugin.configs["core-web-vitals"].rules,
  },
  parser: require.resolve("next/dist/compiled/babel/eslint-parser"),
  parserOptions: {
    requireConfigFile: false,
    babelOptions: { parserOpts: { plugins: ["typescript", "jsx"] } },
    ecmaVersion: 2022,
    sourceType: "module",
  },
  env: { browser: true, node: true, es2022: true },
};
