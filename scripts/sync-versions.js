#!/usr/bin/env node

/**
 * Sync version from root package.json to all workspace packages
 * This ensures all packages maintain the same version number
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read root package.json
const rootPackagePath = path.join(__dirname, '..', 'package.json');
const rootPackage = JSON.parse(fs.readFileSync(rootPackagePath, 'utf8'));
const newVersion = rootPackage.version;

console.log(`🔄 Syncing version ${newVersion} to all workspaces...`);

// Get workspaces from root package.json
const workspaces = rootPackage.workspaces || [];

workspaces.forEach(workspace => {
  const packagePath = path.join(__dirname, '..', workspace, 'package.json');

  if (fs.existsSync(packagePath)) {
    const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
    const oldVersion = packageJson.version;

    packageJson.version = newVersion;

    fs.writeFileSync(packagePath, JSON.stringify(packageJson, null, 2) + '\n');
    console.log(`  ✅ ${workspace}: ${oldVersion} → ${newVersion}`);
  } else {
    console.log(`  ⚠️  ${workspace}: package.json not found`);
  }
});

console.log('✨ Version sync complete!');
