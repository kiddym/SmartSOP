/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#d97757',
          dark: '#ae5f46',
        },
      },
      fontFamily: {
        sans: [
          'PingFang SC',
          'Microsoft YaHei',
          'Helvetica Neue',
          'Arial',
          'sans-serif',
        ],
        display: ['Fraunces', 'Georgia', 'Times New Roman', 'serif'],
        // mono: 数据字段（编号/版本/日期/状态枚举），权威见 docs/design-system.md §2.2。
        // 与 tokens.css --font-mono 保持同步；任何一处变动需双向回填。
        mono: [
          'JetBrains Mono',
          'Sarasa Mono SC',
          'ui-monospace',
          'SFMono-Regular',
          'Menlo',
          'Consolas',
          'Liberation Mono',
          'Courier New',
          'monospace',
        ],
      },
    },
  },
  plugins: [],
  corePlugins: {
    // Element Plus 自带 preflight，避免冲突
    preflight: false,
  },
}
