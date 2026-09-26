import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'.',testMatch:'*.spec.js',workers:1,timeout:180000,
  outputDir:'../../.artifacts/browser',
  use:{baseURL:process.env.FLOWERMOON_TEST_URL||'http://localhost:8000',viewport:{width:1440,height:1000},screenshot:'only-on-failure',trace:'retain-on-failure'},
  reporter:[['list']]
});
