#!/usr/bin/env node

/**
 * Setup Git Commit Message Template
 * Configures git to use the .gitmessage template for commit messages
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';

/**
 * Setup git commit message template
 */
function setupGitTemplate() {
  const templatePath = '.gitmessage';

  // Check if template file exists
  if (!fs.existsSync(templatePath)) {
    console.error(`❌ Template file ${templatePath} not found`);
    process.exit(1);
  }

  try {
    // Configure git to use the template
    execSync(`git config commit.template ${templatePath}`, { stdio: 'inherit' });
    console.log(`✅ Git commit template configured to use ${templatePath}`);

    // Also set it globally for the user (optional)
    const globalSetup = process.argv.includes('--global');
    if (globalSetup) {
      const absolutePath = path.resolve(templatePath);
      execSync(`git config --global commit.template ${absolutePath}`, { stdio: 'inherit' });
      console.log(`✅ Global git commit template configured to use ${absolutePath}`);
    }

    console.log('\n📝 Usage:');
    console.log('  - Run "git commit" (without -m) to use the template');
    console.log('  - Or use "yarn commit" for interactive commit helper');
    console.log('  - Template provides guidance for conventional commit format');
  } catch (error) {
    console.error('❌ Failed to configure git template:', error.message);
    process.exit(1);
  }
}

// CLI interface
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log('🔧 Setting up Git Commit Message Template\n');
  setupGitTemplate();
}

export { setupGitTemplate };
