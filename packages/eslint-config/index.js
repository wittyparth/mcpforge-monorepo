import base from '@vercel/style-guide/eslint/node.js';

/** @type {import("eslint").Linter.Config[]} */
export default [
  ...base,
  {
    ignores: ['.next/**', 'dist/**', 'build/**', 'node_modules/**', '.turbo/**', 'coverage/**'],
  },
  {
    rules: {
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/consistent-type-imports': 'error',
    },
  },
];
