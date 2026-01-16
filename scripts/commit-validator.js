#!/usr/bin/env node

/**
 * Comprehensive Commit Message Validator
 * Implements conventional commit parsing and validation with detailed error messages
 */

import fs from 'fs';
import path from 'path';

// Configuration for commit validation
const COMMIT_CONFIG = {
  types: [
    'feat', // New feature
    'fix', // Bug fix
    'docs', // Documentation
    'style', // Code style changes
    'refactor', // Code refactoring
    'test', // Adding tests
    'chore', // Maintenance tasks
    'perf', // Performance improvements
    'ci', // CI/CD changes
    'build', // Build system changes
  ],
  scopes: [
    'app', // CDK Application module
    'firewall', // Network Firewall module
    'vpc', // VPC module
    'shared', // Shared utilities
    'scripts', // Build/deployment scripts
    'docs', // Documentation
    'config', // Configuration files
    'ci', // CI/CD workflows
  ],
  maxSubjectLength: 72,
  maxBodyLineLength: 100,
  requireScope: true,
  requireBody: false,
  requireFooter: false,
};

/**
 * Parse a conventional commit message
 * @param {string} message - The commit message to parse
 * @returns {Object} Parsed commit object or null if invalid
 */
function parseCommitMessage(message) {
  const lines = message.trim().split('\n');
  const subject = lines[0];

  // Regex for conventional commit format: type(scope): description
  const conventionalCommitRegex = /^(\w+)(?:\(([^)]+)\))?: ?(.*)$/;
  const match = subject.match(conventionalCommitRegex);

  if (!match) {
    return null;
  }

  const [, type, scope, description] = match;

  // Parse body and footer
  let body = '';
  let footer = '';
  let breakingChange = '';

  if (lines.length > 1) {
    const bodyLines = [];
    const footerLines = [];
    let inFooter = false;

    for (let i = 2; i < lines.length; i++) {
      const line = lines[i];

      // Check for breaking change or footer patterns
      if (
        line.startsWith('BREAKING CHANGE:') ||
        line.match(/^[\w-]+: .+/) ||
        line.match(/^Closes #\d+/) ||
        line.match(/^Fixes #\d+/)
      ) {
        inFooter = true;
      }

      if (inFooter) {
        footerLines.push(line);
        if (line.startsWith('BREAKING CHANGE:')) {
          breakingChange = line.substring('BREAKING CHANGE:'.length).trim();
        }
      } else if (line.trim() !== '') {
        bodyLines.push(line);
      }
    }

    body = bodyLines.join('\n').trim();
    footer = footerLines.join('\n').trim();
  }

  return {
    type,
    scope,
    description,
    body,
    footer,
    breakingChange,
    subject,
    raw: message,
  };
}

/**
 * Validate a parsed commit message
 * @param {Object} commit - Parsed commit object
 * @returns {Object} Validation result with errors and warnings
 */
function validateCommit(commit) {
  const errors = [];
  const warnings = [];

  if (!commit) {
    errors.push({
      code: 'INVALID_FORMAT',
      message: 'Commit message does not follow conventional commit format',
      details: 'Expected format: type(scope): description',
      example: 'feat(app): add user authentication system',
    });
    return { valid: false, errors, warnings };
  }

  // Validate type
  if (!COMMIT_CONFIG.types.includes(commit.type)) {
    errors.push({
      code: 'INVALID_TYPE',
      message: `Invalid commit type: "${commit.type}"`,
      details: `Allowed types: ${COMMIT_CONFIG.types.join(', ')}`,
      example: 'feat(app): add new feature',
    });
  }

  // Validate scope
  if (COMMIT_CONFIG.requireScope && !commit.scope) {
    errors.push({
      code: 'MISSING_SCOPE',
      message: 'Commit scope is required',
      details: `Available scopes: ${COMMIT_CONFIG.scopes.join(', ')}`,
      example: 'feat(app): add new feature',
    });
  } else if (commit.scope && !COMMIT_CONFIG.scopes.includes(commit.scope)) {
    errors.push({
      code: 'INVALID_SCOPE',
      message: `Invalid commit scope: "${commit.scope}"`,
      details: `Allowed scopes: ${COMMIT_CONFIG.scopes.join(', ')}`,
      example: 'feat(app): add new feature',
    });
  }

  // Validate description
  if (!commit.description || commit.description.trim().length === 0) {
    errors.push({
      code: 'MISSING_DESCRIPTION',
      message: 'Commit description is required',
      details: 'Description should be a brief summary of the change',
      example: 'feat(app): add user authentication system',
    });
  }

  // Validate subject length
  if (commit.subject.length > COMMIT_CONFIG.maxSubjectLength) {
    errors.push({
      code: 'SUBJECT_TOO_LONG',
      message: `Subject line too long: ${commit.subject.length} characters`,
      details: `Maximum allowed: ${COMMIT_CONFIG.maxSubjectLength} characters`,
      example: 'Keep the subject line concise and under 72 characters',
    });
  }

  // Validate description format
  if (commit.description) {
    if (commit.description.endsWith('.')) {
      warnings.push({
        code: 'DESCRIPTION_ENDS_WITH_PERIOD',
        message: 'Description should not end with a period',
        details: 'Use imperative mood without trailing punctuation',
        example: 'add user authentication (not "adds user authentication.")',
      });
    }

    if (commit.description[0] !== commit.description[0].toLowerCase()) {
      warnings.push({
        code: 'DESCRIPTION_NOT_LOWERCASE',
        message: 'Description should start with lowercase letter',
        details: 'Use imperative mood starting with lowercase',
        example: 'add user authentication (not "Add user authentication")',
      });
    }
  }

  // Validate body line length
  if (commit.body) {
    const bodyLines = commit.body.split('\n');
    for (let i = 0; i < bodyLines.length; i++) {
      if (bodyLines[i].length > COMMIT_CONFIG.maxBodyLineLength) {
        warnings.push({
          code: 'BODY_LINE_TOO_LONG',
          message: `Body line ${i + 1} too long: ${bodyLines[i].length} characters`,
          details: `Maximum recommended: ${COMMIT_CONFIG.maxBodyLineLength} characters`,
          example: 'Break long lines into multiple shorter lines',
        });
      }
    }
  }

  // Validate breaking changes
  if (commit.breakingChange && commit.type !== 'feat' && commit.type !== 'fix') {
    warnings.push({
      code: 'BREAKING_CHANGE_TYPE',
      message: 'Breaking changes are typically associated with feat or fix types',
      details: 'Consider if this should be a feat or fix type',
      example: 'feat(app)!: change API response format',
    });
  }

  return {
    valid: errors.length === 0,
    errors,
    warnings,
  };
}

/**
 * Format validation errors and warnings for display
 * @param {Object} validation - Validation result
 * @returns {string} Formatted error message
 */
function formatValidationMessage(validation) {
  let message = '';

  if (validation.errors.length > 0) {
    message += '❌ COMMIT MESSAGE VALIDATION FAILED\n\n';

    validation.errors.forEach((error, index) => {
      message += `${index + 1}. ${error.message}\n`;
      message += `   ${error.details}\n`;
      if (error.example) {
        message += `   Example: ${error.example}\n`;
      }
      message += '\n';
    });
  }

  if (validation.warnings.length > 0) {
    message += '⚠️  WARNINGS\n\n';

    validation.warnings.forEach((warning, index) => {
      message += `${index + 1}. ${warning.message}\n`;
      message += `   ${warning.details}\n`;
      if (warning.example) {
        message += `   Example: ${warning.example}\n`;
      }
      message += '\n';
    });
  }

  if (validation.valid) {
    message += '✅ COMMIT MESSAGE IS VALID\n\n';
  } else {
    message += '� TIP: Use `make commit` for guided commit creation\n\n';
    message += '📝 CONVENTIONAL COMMIT FORMAT:\n';
    message += '   type(scope): description\n\n';
    message += '   [optional body]\n\n';
    message += '   [optional footer(s)]\n\n';
    message += `📋 AVAILABLE TYPES: ${COMMIT_CONFIG.types.join(', ')}\n`;
    message += `📦 AVAILABLE SCOPES: ${COMMIT_CONFIG.scopes.join(', ')}\n\n`;
    message += '💡 EXAMPLES:\n';
    message += '   feat(app): add user authentication system\n';
    message += '   fix(firewall): resolve rule parsing issue\n';
    message += '   docs(shared): update API documentation\n';
    message += '   refactor(vpc): simplify subnet configuration\n\n';
  }

  return message;
}

/**
 * Main validation function
 * @param {string} commitMessage - The commit message to validate
 * @returns {Object} Validation result
 */
function validateCommitMessage(commitMessage) {
  const parsed = parseCommitMessage(commitMessage);
  const validation = validateCommit(parsed);

  return {
    parsed,
    validation,
    message: formatValidationMessage(validation),
  };
}

// CLI interface
if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Usage: commit-validator.js <commit-message-file>');
    process.exit(1);
  }

  const commitMessageFile = args[0];

  try {
    const commitMessage = fs.readFileSync(commitMessageFile, 'utf8').trim();
    const result = validateCommitMessage(commitMessage);

    console.log(result.message);

    if (!result.validation.valid) {
      process.exit(1);
    }
  } catch (error) {
    console.error('Error reading commit message file:', error.message);
    process.exit(1);
  }
}

export { validateCommitMessage, parseCommitMessage, validateCommit, COMMIT_CONFIG };
