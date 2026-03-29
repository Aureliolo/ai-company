/** @type {import('@lhci/utils').Config} */
export default {
  ci: {
    collect: {
      numberOfRuns: 3,
      startServerCommand: 'npm run preview',
      startServerReadyPattern: 'Local:',
      url: ['http://localhost:4173/login'],
      settings: {
        preset: 'desktop',
        chromeFlags: '--headless --no-sandbox',
      },
    },
    assert: {
      assertions: {
        'categories:performance': ['warn', { minScore: 0.9 }],
        'categories:accessibility': ['warn', { minScore: 0.9 }],
        'categories:best-practices': ['warn', { minScore: 0.9 }],
      },
    },
    upload: {
      target: 'temporary-public-storage',
    },
  },
}
