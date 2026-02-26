/**
 * Custom Vitest reporter that collects accessibility (axe) test results
 * and writes a summary to coverage/a11y-report.json and coverage/a11y-report.html.
 */
import type { Reporter, TestModule } from 'vitest/node';
import * as fs from 'node:fs';
import * as path from 'node:path';

const A11Y_INDICATORS = [
  'accessibility',
  'a11y',
  'violations',
  'axe',
  'no accessibility violations',
];

function isA11yTest(fullName: string, moduleId?: string): boolean {
  const lower = fullName.toLowerCase();
  const id = (moduleId ?? '').toLowerCase();
  return (
    A11Y_INDICATORS.some((k) => lower.includes(k)) ||
    A11Y_INDICATORS.some((k) => id.includes(k))
  );
}

function collectA11yTests(testModules: ReadonlyArray<TestModule>) {
  const tests: Array<{ fullName: string; state: string; moduleId: string }> = [];
  for (const module of testModules) {
    for (const testCase of module.children.allTests()) {
      const fullName = testCase.fullName;
      if (isA11yTest(fullName, module.moduleId)) {
        const result = testCase.result();
        tests.push({
          fullName,
          state: result?.state ?? 'pending',
          moduleId: module.moduleId ?? 'unknown',
        });
      }
    }
  }
  return tests;
}

const a11yReporter: Reporter = {
  onTestRunEnd(testModules) {
    const a11yTests = collectA11yTests(testModules);
    const passed = a11yTests.filter((t) => t.state === 'passed').length;
    const failed = a11yTests.filter((t) => t.state === 'failed').length;
    const skipped = a11yTests.filter((t) => t.state === 'skipped').length;

    const report = {
      timestamp: new Date().toISOString(),
      summary: { total: a11yTests.length, passed, failed, skipped },
      tests: a11yTests,
    };

    const root = process.cwd();
    const coverageDir = path.join(root, 'coverage');
    if (!fs.existsSync(coverageDir)) {
      fs.mkdirSync(coverageDir, { recursive: true });
    }

    const jsonPath = path.join(coverageDir, 'a11y-report.json');
    fs.writeFileSync(jsonPath, JSON.stringify(report, null, 2), 'utf-8');

    const htmlPath = path.join(coverageDir, 'a11y-report.html');
    const html = generateHtmlReport(report);
    fs.writeFileSync(htmlPath, html, 'utf-8');
  },
};

export default a11yReporter;

function generateHtmlReport(report: {
  timestamp: string;
  summary: { total: number; passed: number; failed: number; skipped: number };
  tests: Array<{ fullName: string; state: string; moduleId: string }>;
}): string {
  const { summary, tests } = report;
  const statusClass = summary.failed > 0 ? 'fail' : 'pass';
  const rows = tests
    .map(
      (t) =>
        `<tr class="${t.state}"><td>${escape(t.fullName)}</td><td>${t.state}</td><td>${escape(t.moduleId)}</td></tr>`,
    )
    .join('');
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Accessibility Test Report</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; max-width: 900px; }
    h1 { font-size: 1.5rem; }
    .summary { display: flex; gap: 1.5rem; margin: 1rem 0; padding: 1rem; border-radius: 8px; }
    .summary.pass { background: #d4edda; color: #155724; }
    .summary.fail { background: #f8d7da; color: #721c24; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { text-align: left; padding: 0.5rem; border-bottom: 1px solid #dee2e6; }
    th { background: #f8f9fa; }
    .passed { color: #28a745; }
    .failed { color: #dc3545; }
    .skipped { color: #6c757d; }
    .meta { color: #6c757d; font-size: 0.875rem; margin-top: 1rem; }
  </style>
</head>
<body>
  <h1>Accessibility (AXE) Test Report</h1>
  <div class="summary ${statusClass}">
    <span><strong>Total:</strong> ${summary.total}</span>
    <span><strong>Passed:</strong> ${summary.passed}</span>
    <span><strong>Failed:</strong> ${summary.failed}</span>
    <span><strong>Skipped:</strong> ${summary.skipped}</span>
  </div>
  <table>
    <thead><tr><th>Test</th><th>Status</th><th>Module</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <p class="meta">Generated: ${report.timestamp}</p>
</body>
</html>`;
}

function escape(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
