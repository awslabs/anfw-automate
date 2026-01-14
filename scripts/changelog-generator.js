#!/usr/bin/env node

/**
 * Changelog Generator for Conventional Commits
 * Generates changelog entries from git commit messages following conventional commit format
 */

import { execSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import { parseCommitMessage } from './commit-validator.js';

/**
 * Get git commits since last tag or all commits
 * @param {string} since - Git reference to start from (tag, commit hash, etc.)
 * @returns {Array} Array of commit objects
 */
function getCommits(since = null) {
  try {
    let gitCommand = 'git log --pretty=format:"%H|%s|%b|%an|%ad" --date=short';

    if (since) {
      gitCommand += ` ${since}..HEAD`;
    }

    const output = execSync(gitCommand, { encoding: 'utf8' });

    if (!output.trim()) {
      return [];
    }

    return output
      .trim()
      .split('\n')
      .map(line => {
        const [hash, subject, body, author, date] = line.split('|');
        const fullMessage = body ? `${subject}\n\n${body}` : subject;

        return {
          hash: hash.substring(0, 7),
          fullHash: hash,
          subject,
          body: body || '',
          author,
          date,
          fullMessage,
          parsed: parseCommitMessage(fullMessage),
        };
      });
  } catch (error) {
    console.error('Error getting git commits:', error.message);
    return [];
  }
}

/**
 * Get the latest git tag
 * @returns {string|null} Latest tag or null if no tags exist
 */
function getLatestTag() {
  try {
    const output = execSync('git describe --tags --abbrev=0', { encoding: 'utf8' });
    return output.trim();
  } catch (error) {
    return null;
  }
}

/**
 * Group commits by type and scope
 * @param {Array} commits - Array of commit objects
 * @returns {Object} Grouped commits
 */
function groupCommits(commits) {
  const groups = {
    feat: { title: '### ✨ Features', items: [] },
    fix: { title: '### 🐛 Bug Fixes', items: [] },
    docs: { title: '### 📚 Documentation', items: [] },
    style: { title: '### 💄 Styles', items: [] },
    refactor: { title: '### ♻️ Code Refactoring', items: [] },
    perf: { title: '### ⚡ Performance Improvements', items: [] },
    test: { title: '### ✅ Tests', items: [] },
    build: { title: '### 🏗️ Build System', items: [] },
    ci: { title: '### 👷 CI/CD', items: [] },
    chore: { title: '### 🔧 Chores', items: [] },
    revert: { title: '### ⏪ Reverts', items: [] },
  };

  const breakingChanges = [];
  const validCommits = commits.filter(commit => commit.parsed && commit.parsed.type);

  validCommits.forEach(commit => {
    const { parsed } = commit;
    const type = parsed.type;

    if (groups[type]) {
      const scopeText = parsed.scope ? `**${parsed.scope}**: ` : '';
      const item = {
        scope: parsed.scope,
        description: parsed.description,
        hash: commit.hash,
        fullHash: commit.fullHash,
        author: commit.author,
        date: commit.date,
        formatted: `- ${scopeText}${parsed.description} ([${commit.hash}](../../commit/${commit.fullHash}))`,
      };

      groups[type].items.push(item);

      // Check for breaking changes
      if (parsed.breakingChange) {
        breakingChanges.push({
          ...item,
          breakingChange: parsed.breakingChange,
          formatted: `- ${scopeText}${parsed.description}\n  \n  **BREAKING CHANGE:** ${parsed.breakingChange} ([${commit.hash}](../../commit/${commit.fullHash}))`,
        });
      }
    }
  });

  return { groups, breakingChanges };
}

/**
 * Generate changelog section for a version
 * @param {string} version - Version number
 * @param {string} date - Release date
 * @param {Array} commits - Array of commits
 * @returns {string} Formatted changelog section
 */
function generateChangelogSection(version, date, commits) {
  const { groups, breakingChanges } = groupCommits(commits);

  let changelog = `## [${version}](../../compare/v${version}...HEAD) (${date})\n\n`;

  // Add breaking changes first if any
  if (breakingChanges.length > 0) {
    changelog += '### ⚠ BREAKING CHANGES\n\n';
    breakingChanges.forEach(change => {
      changelog += `${change.formatted}\n\n`;
    });
  }

  // Add other changes by type
  Object.entries(groups).forEach(([type, group]) => {
    if (group.items.length > 0) {
      changelog += `${group.title}\n\n`;

      // Group by scope within each type
      const byScope = {};
      group.items.forEach(item => {
        const scope = item.scope || 'general';
        if (!byScope[scope]) {
          byScope[scope] = [];
        }
        byScope[scope].push(item);
      });

      // Sort scopes alphabetically
      const sortedScopes = Object.keys(byScope).sort();
      sortedScopes.forEach(scope => {
        byScope[scope].forEach(item => {
          changelog += `${item.formatted}\n`;
        });
      });

      changelog += '\n';
    }
  });

  return changelog;
}

/**
 * Update CHANGELOG.md file
 * @param {string} version - Version number
 * @param {string} changelogSection - New changelog section
 */
function updateChangelogFile(version, changelogSection) {
  const changelogPath = 'CHANGELOG.md';
  let existingContent = '';

  try {
    existingContent = fs.readFileSync(changelogPath, 'utf8');
  } catch (error) {
    // Create new changelog if it doesn't exist
    existingContent =
      '# Changelog\n\nAll notable changes to this project will be documented in this file. See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.\n\n';
  }

  // Find where to insert the new section
  const lines = existingContent.split('\n');
  const headerEndIndex = lines.findIndex(line => line.startsWith('## '));

  if (headerEndIndex === -1) {
    // No existing versions, append to end
    const newContent = existingContent + changelogSection;
    fs.writeFileSync(changelogPath, newContent);
  } else {
    // Insert before first existing version
    const beforeVersion = lines.slice(0, headerEndIndex).join('\n');
    const afterVersion = lines.slice(headerEndIndex).join('\n');
    const newContent = beforeVersion + '\n' + changelogSection + afterVersion;
    fs.writeFileSync(changelogPath, newContent);
  }

  console.log(`✅ Updated ${changelogPath} with version ${version}`);
}

/**
 * Generate changelog for unreleased changes
 * @param {string} since - Git reference to start from
 */
function generateUnreleasedChangelog(since = null) {
  const commits = getCommits(since);

  if (commits.length === 0) {
    console.log('No commits found for changelog generation');
    return;
  }

  console.log(`Found ${commits.length} commits for changelog generation`);

  const { groups, breakingChanges } = groupCommits(commits);

  console.log('\n📋 UNRELEASED CHANGES:\n');

  // Show breaking changes first
  if (breakingChanges.length > 0) {
    console.log('⚠️  BREAKING CHANGES:');
    breakingChanges.forEach(change => {
      console.log(`  - ${change.scope ? `${change.scope}: ` : ''}${change.description}`);
      console.log(`    BREAKING CHANGE: ${change.breakingChange}`);
    });
    console.log('');
  }

  // Show other changes by type
  Object.entries(groups).forEach(([type, group]) => {
    if (group.items.length > 0) {
      console.log(`${group.title.replace('### ', '').replace(/[^\w\s]/g, '')}:`);
      group.items.forEach(item => {
        console.log(`  - ${item.scope ? `${item.scope}: ` : ''}${item.description} (${item.hash})`);
      });
      console.log('');
    }
  });
}

/**
 * Main CLI interface
 */
function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  switch (command) {
    case 'unreleased':
      const since = args[1] || getLatestTag();
      console.log(`Generating changelog since: ${since || 'beginning'}`);
      generateUnreleasedChangelog(since);
      break;

    case 'release':
      const version = args[1];
      const date = args[2] || new Date().toISOString().split('T')[0];

      if (!version) {
        console.error('Usage: changelog-generator.js release <version> [date]');
        process.exit(1);
      }

      const latestTag = getLatestTag();
      const commits = getCommits(latestTag);

      if (commits.length === 0) {
        console.log('No commits found for release');
        return;
      }

      const changelogSection = generateChangelogSection(version, date, commits);
      updateChangelogFile(version, changelogSection);
      break;

    case 'preview':
      const previewSince = args[1] || getLatestTag();
      const previewVersion = args[2] || 'UNRELEASED';
      const previewDate = new Date().toISOString().split('T')[0];

      console.log(`Previewing changelog since: ${previewSince || 'beginning'}`);
      const previewCommits = getCommits(previewSince);

      if (previewCommits.length === 0) {
        console.log('No commits found for preview');
        return;
      }

      const previewSection = generateChangelogSection(previewVersion, previewDate, previewCommits);
      console.log('\n📋 CHANGELOG PREVIEW:\n');
      console.log(previewSection);
      break;

    default:
      console.log('📝 Changelog Generator for Conventional Commits\n');
      console.log('Usage:');
      console.log('  changelog-generator.js unreleased [since]  - Show unreleased changes');
      console.log('  changelog-generator.js release <version>   - Generate release changelog');
      console.log('  changelog-generator.js preview [since]     - Preview changelog format');
      console.log('\nExamples:');
      console.log('  changelog-generator.js unreleased v2.0.0');
      console.log('  changelog-generator.js release v2.1.0');
      console.log('  changelog-generator.js preview');
      break;
  }
}

// Run CLI if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

export { getCommits, groupCommits, generateChangelogSection, updateChangelogFile };
