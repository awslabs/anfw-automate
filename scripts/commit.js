#!/usr/bin/env node

import { execSync } from 'child_process';
import readline from 'readline';

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
});

// Most commonly used types - simplified
const types = [
  { value: 'feat', description: 'New feature' },
  { value: 'fix', description: 'Bug fix' },
  { value: 'docs', description: 'Documentation' },
  { value: 'refactor', description: 'Code refactoring' },
  { value: 'ci', description: 'CI/CD changes' },
  { value: 'chore', description: 'Maintenance' },
];

// Project modules as scopes - these are the main focus
const scopes = [
  { value: 'app', description: 'CDK Application module' },
  { value: 'firewall', description: 'Network Firewall module' },
  { value: 'vpc', description: 'VPC module' },
  { value: 'shared', description: 'Shared utilities' },
  { value: 'scripts', description: 'Build/deployment scripts' },
  { value: 'docs', description: 'Documentation' },
  { value: 'config', description: 'Configuration files' },
  { value: 'ci', description: 'CI/CD workflows' },
];

console.log('\n🚀 Conventional Commit Helper\n');

// Focus on scopes first (project modules)
console.log("📦 Select the module/scope you're working on:");
scopes.forEach((scope, index) => {
  console.log(`  ${index + 1}. ${scope.value}: ${scope.description}`);
});

rl.question('\nSelect scope (1-8): ', scopeIndex => {
  const selectedScope = scopes[parseInt(scopeIndex) - 1];
  if (!selectedScope) {
    console.log('Invalid selection');
    process.exit(1);
  }

  console.log(`\n🔧 What type of change is this for ${selectedScope.value}?`);
  types.forEach((type, index) => {
    console.log(`  ${index + 1}. ${type.value}: ${type.description}`);
  });

  rl.question('\nSelect type (1-6): ', typeIndex => {
    const selectedType = types[parseInt(typeIndex) - 1];
    if (!selectedType) {
      console.log('Invalid selection');
      process.exit(1);
    }

    rl.question('\n📝 Enter description: ', description => {
      if (!description) {
        console.log('Description is required');
        process.exit(1);
      }

      rl.question('\n📄 Enter body (optional): ', body => {
        rl.question('\n⚠️  Enter breaking changes (optional): ', breaking => {
          let commitMessage = `${selectedType.value}(${selectedScope.value}): ${description}`;

          if (body) {
            commitMessage += `\n\n${body}`;
          }

          if (breaking) {
            commitMessage += `\n\nBREAKING CHANGE: ${breaking}`;
          }

          console.log('\n📋 Commit message:');
          console.log('---');
          console.log(commitMessage);
          console.log('---');

          rl.question('\n✅ Proceed with commit? (y/N): ', confirm => {
            if (confirm.toLowerCase() === 'y' || confirm.toLowerCase() === 'yes') {
              try {
                execSync(`git commit -m "${commitMessage.replace(/"/g, '\\"')}"`, {
                  stdio: 'inherit',
                });
                console.log('\n🎉 Commit successful!');
              } catch (error) {
                console.error('\n❌ Commit failed:', error.message);
                process.exit(1);
              }
            } else {
              console.log('\n❌ Commit cancelled');
            }
            rl.close();
          });
        });
      });
    });
  });
});
