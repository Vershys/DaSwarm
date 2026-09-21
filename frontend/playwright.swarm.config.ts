import { defineConfig } from '@playwright/test'
export default defineConfig({testDir:'./e2e',testMatch:'swarm.spec.ts',workers:1,timeout:60000,
  use:{baseURL:process.env.SWARM_BASE_URL||'http://localhost:5173',viewport:{width:1600,height:1000},screenshot:'only-on-failure',trace:'retain-on-failure'},
  reporter:[['list'],['junit',{outputFile:'../test-evidence/swarm-browser.xml'}]]})
