const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests/e2e",
  testMatch: "**/*.spec.js",
  fullyParallel: false,
  forbidOnly: true,
  use: {
    headless: true,
    trace: "retain-on-failure"
  }
});
