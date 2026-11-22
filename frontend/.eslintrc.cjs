// ESLint 8 configuration for JavaScript and native Node test files.
// TypeScript is checked independently with strict tsc --noEmit in npm run lint.
module.exports = {
  root: true,
  env: { browser: true, node: true, es2022: true },
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  extends: ['eslint:recommended'],
  ignorePatterns: ['node_modules/', 'dist/'],
};
