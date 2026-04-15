/**
 * Lighthouse CI budget + assertions for the GARL frontend.
 * The .github/workflows/lighthouse.yml consumes this when invoked
 * with `lhci collect --config ./lighthouserc.js`.
 */
module.exports = {
  ci: {
    collect: {
      settings: { preset: "desktop" },
      numberOfRuns: 3,
      url: [
        "https://garl.ai/",
        "https://garl.ai/for-code",
        "https://garl.ai/r/6ff83db8",
        "https://garl.ai/compliance",
        "https://garl.ai/docs",
      ],
    },
    assert: {
      preset: "lighthouse:no-pwa",
      assertions: {
        "categories:performance": ["error", { minScore: 0.85 }],
        "categories:accessibility": ["warn", { minScore: 0.9 }],
        "categories:best-practices": ["warn", { minScore: 0.9 }],
        "largest-contentful-paint": ["error", { maxNumericValue: 2500 }],
        "cumulative-layout-shift": ["error", { maxNumericValue: 0.1 }],
        "total-blocking-time": ["error", { maxNumericValue: 300 }],
        "first-contentful-paint": ["warn", { maxNumericValue: 2000 }],
      },
    },
    budgets: [
      {
        path: "/*",
        resourceSizes: [
          { resourceType: "script", budget: 200 },
          { resourceType: "image", budget: 400 },
          { resourceType: "total", budget: 800 },
        ],
      },
    ],
    upload: {
      target: "filesystem",
      outputDir: ".lhci-report",
    },
  },
};
