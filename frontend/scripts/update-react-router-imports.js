#!/usr/bin/env node

/**
 * Script to update all imports from 'react-router-dom' to 'react-router'
 * for React Router v7 migration.
 */

const fs = require('fs');
const path = require('path');

const FRONTEND_DIR = path.join(__dirname, '..');
const EXTENSIONS = ['.ts', '.tsx', '.js', '.jsx'];

// Patterns to match various import styles
const IMPORT_PATTERNS = [
  // Standard imports
  /import\s+({[^}]+}|[^'"]+?)\s+from\s+['"]react-router-dom['"]/g,
  // Type imports
  /import\s+type\s+({[^}]+}|[^'"]+?)\s+from\s+['"]react-router-dom['"]/g,
  // Side-effect imports
  /import\s+['"]react-router-dom['"]/g,
  // Dynamic imports (less common but possible)
  /import\s*\(['"]react-router-dom['"]\)/g,
];

/**
 * Recursively find all files with matching extensions
 */
function findFiles(dir, fileList = []) {
  const files = fs.readdirSync(dir);

  files.forEach((file) => {
    const filePath = path.join(dir, file);
    const stat = fs.statSync(filePath);

    if (stat.isDirectory()) {
      // Skip node_modules, .git, dist, build, coverage, etc.
      if (
        !file.startsWith('.') &&
        file !== 'node_modules' &&
        file !== 'dist' &&
        file !== 'build' &&
        file !== 'coverage'
      ) {
        findFiles(filePath, fileList);
      }
    } else if (EXTENSIONS.some((ext) => file.endsWith(ext))) {
      fileList.push(filePath);
    }
  });

  return fileList;
}

/**
 * Update imports in a file
 */
function updateImports(filePath) {
  let content = fs.readFileSync(filePath, 'utf8');
  let modified = false;
  let changes = [];

  IMPORT_PATTERNS.forEach((pattern) => {
    const matches = content.matchAll(pattern);
    for (const match of matches) {
      const original = match[0];
      const updated = original.replace(/react-router-dom/g, 'react-router');
      changes.push({ original, updated });
    }
  });

  if (changes.length > 0) {
    content = content.replace(/react-router-dom/g, 'react-router');
    modified = true;
  }

  return { content, modified, changes };
}

/**
 * Main function
 */
function main() {
  const files = findFiles(FRONTEND_DIR);
  const updates = [];

  console.log(`\n🔍 Scanning ${files.length} files for react-router-dom imports...\n`);

  // First pass: collect all changes
  files.forEach((filePath) => {
    const { modified, changes } = updateImports(filePath);
    if (modified) {
      const relativePath = path.relative(FRONTEND_DIR, filePath);
      updates.push({
        filePath,
        relativePath,
        changes,
      });
    }
  });

  if (updates.length === 0) {
    console.log('✅ No files found with react-router-dom imports.\n');
    return;
  }

  // Show summary
  console.log(`📋 Found ${updates.length} files with react-router-dom imports:\n`);

  updates.forEach((update) => {
    console.log(`  ${update.relativePath}`);
    update.changes.forEach((change) => {
      console.log(`    - ${change.original.trim()}`);
      console.log(`    + ${change.updated.trim()}`);
    });
    console.log('');
  });

  // Ask for confirmation
  const readline = require('readline');
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  rl.question(
    `\n❓ Update ${updates.length} files? (yes/no): `,
    (answer) => {
      if (answer.toLowerCase() === 'yes' || answer.toLowerCase() === 'y') {
        console.log('\n🔄 Updating files...\n');

        updates.forEach((update) => {
          const { content } = updateImports(update.filePath);
          fs.writeFileSync(update.filePath, content, 'utf8');
          console.log(`  ✅ Updated: ${update.relativePath}`);
        });

        console.log(`\n✨ Successfully updated ${updates.length} files!\n`);
      } else {
        console.log('\n❌ Update cancelled.\n');
      }
      rl.close();
    }
  );
}

// Run the script
main();
