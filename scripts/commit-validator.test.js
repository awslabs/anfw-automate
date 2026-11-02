#!/usr/bin/env node

/**
 * Tests for commit message validator
 */

import {
  validateCommitMessage,
  parseCommitMessage,
  validateCommit,
  COMMIT_CONFIG,
} from './commit-validator.js';

// Test cases for commit message validation
const testCases = [
  // Valid commit messages
  {
    name: 'Valid feat commit with scope',
    message: 'feat(app): add user authentication system',
    expectedValid: true,
    expectedType: 'feat',
    expectedScope: 'app',
    expectedDescription: 'add user authentication system',
  },
  {
    name: 'Valid fix commit with body',
    message:
      'fix(firewall): resolve rule parsing issue\n\nThis fixes an issue where complex rules were not parsed correctly.\nThe parser now handles nested conditions properly.',
    expectedValid: true,
    expectedType: 'fix',
    expectedScope: 'firewall',
  },
  {
    name: 'Valid commit with breaking change',
    message:
      'feat(shared): update API response format\n\nBREAKING CHANGE: API now returns data in different structure',
    expectedValid: true,
    expectedType: 'feat',
    expectedScope: 'shared',
  },

  // Invalid commit messages
  {
    name: 'Invalid format - no colon',
    message: 'feat(app) add user authentication',
    expectedValid: false,
    expectedErrors: ['INVALID_FORMAT'],
  },
  {
    name: 'Invalid type',
    message: 'feature(app): add user authentication',
    expectedValid: false,
    expectedErrors: ['INVALID_TYPE'],
  },
  {
    name: 'Missing scope',
    message: 'feat: add user authentication',
    expectedValid: false,
    expectedErrors: ['MISSING_SCOPE'],
  },
  {
    name: 'Invalid scope',
    message: 'feat(invalid): add user authentication',
    expectedValid: false,
    expectedErrors: ['INVALID_SCOPE'],
  },
  {
    name: 'Missing description',
    message: 'feat(app): ',
    expectedValid: false,
    expectedErrors: ['MISSING_DESCRIPTION'],
  },
  {
    name: 'Subject too long',
    message:
      'feat(app): this is a very long commit message that exceeds the maximum allowed length for a subject line and should trigger a validation error',
    expectedValid: false,
    expectedErrors: ['SUBJECT_TOO_LONG'],
  },

  // Warning cases
  {
    name: 'Description ends with period',
    message: 'feat(app): add user authentication.',
    expectedValid: true,
    expectedWarnings: ['DESCRIPTION_ENDS_WITH_PERIOD'],
  },
  {
    name: 'Description starts with uppercase',
    message: 'feat(app): Add user authentication',
    expectedValid: true,
    expectedWarnings: ['DESCRIPTION_NOT_LOWERCASE'],
  },
];

/**
 * Run a single test case
 */
function runTest(testCase) {
  console.log(`\n🧪 Testing: ${testCase.name}`);
  console.log(`   Message: "${testCase.message.split('\n')[0]}"`);

  try {
    const result = validateCommitMessage(testCase.message);
    const { parsed, validation } = result;

    // Check validity
    if (validation.valid !== testCase.expectedValid) {
      console.log(`   ❌ Expected valid: ${testCase.expectedValid}, got: ${validation.valid}`);
      return false;
    }

    // Check parsed fields for valid messages
    if (testCase.expectedValid && parsed) {
      if (testCase.expectedType && parsed.type !== testCase.expectedType) {
        console.log(`   ❌ Expected type: ${testCase.expectedType}, got: ${parsed.type}`);
        return false;
      }

      if (testCase.expectedScope && parsed.scope !== testCase.expectedScope) {
        console.log(`   ❌ Expected scope: ${testCase.expectedScope}, got: ${parsed.scope}`);
        return false;
      }

      if (testCase.expectedDescription && parsed.description !== testCase.expectedDescription) {
        console.log(
          `   ❌ Expected description: ${testCase.expectedDescription}, got: ${parsed.description}`
        );
        return false;
      }
    }

    // Check expected errors
    if (testCase.expectedErrors) {
      const errorCodes = validation.errors.map(e => e.code);
      for (const expectedError of testCase.expectedErrors) {
        if (!errorCodes.includes(expectedError)) {
          console.log(`   ❌ Expected error: ${expectedError}, got: ${errorCodes.join(', ')}`);
          return false;
        }
      }
    }

    // Check expected warnings
    if (testCase.expectedWarnings) {
      const warningCodes = validation.warnings.map(w => w.code);
      for (const expectedWarning of testCase.expectedWarnings) {
        if (!warningCodes.includes(expectedWarning)) {
          console.log(
            `   ❌ Expected warning: ${expectedWarning}, got: ${warningCodes.join(', ')}`
          );
          return false;
        }
      }
    }

    console.log('   ✅ Test passed');
    return true;
  } catch (error) {
    console.log(`   ❌ Test failed with error: ${error.message}`);
    return false;
  }
}

/**
 * Run all tests
 */
function runAllTests() {
  console.log('🚀 Running Commit Validator Tests\n');

  let passed = 0;
  let failed = 0;

  for (const testCase of testCases) {
    if (runTest(testCase)) {
      passed++;
    } else {
      failed++;
    }
  }

  console.log(`\n📊 Test Results:`);
  console.log(`   ✅ Passed: ${passed}`);
  console.log(`   ❌ Failed: ${failed}`);
  console.log(`   📈 Total: ${passed + failed}`);

  if (failed > 0) {
    console.log('\n❌ Some tests failed');
    process.exit(1);
  } else {
    console.log('\n🎉 All tests passed!');
  }
}

// Run tests if this file is executed directly
if (import.meta.url === `file://${process.argv[1]}`) {
  runAllTests();
}
