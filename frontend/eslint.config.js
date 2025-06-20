import js from '@eslint/js';
import vue from 'eslint-plugin-vue';

export default [
  js.configs.recommended,
  {
    files: ['**/*.vue', '**/*.js'],
    plugins: { vue },
    rules: {
      'vue/no-multiple-template-root': 'off',
    },
  },
];
