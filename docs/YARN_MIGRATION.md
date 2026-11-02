# Yarn Migration Guide

## ⚠️ BREAKING CHANGE

This project has migrated from npm to Yarn 4.12.0. **This is a breaking change**
that requires action from all contributors and users.

### Why This is Breaking

- All npm commands (`npm install`, `npm test`, etc.) will no longer work
- CI/CD pipelines using npm must be updated
- Scripts and automation using npm/npx must be updated
- `package-lock.json` is replaced by `yarn.lock`

### Benefits

- **Performance**: Faster installs with Yarn's improved caching
- **Security**: Better security scanning with `yarn npm audit`
- **Workspace Management**: Enhanced monorepo support
- **Consistency**: Deterministic installs with `yarn.lock`

## 🚀 Required Migration Steps for Existing Contributors

### 1. Install Yarn

```bash
# Enable corepack (recommended - comes with Node.js 16.10+)
corepack enable

# Or install globally via npm (if corepack is not available)
npm install -g yarn

# Verify installation
yarn --version  # Should show 4.12.0 or higher
```

### 2. Clean Up Old Dependencies

```bash
# Remove old npm artifacts
rm -rf node_modules package-lock.json

# Install with Yarn
yarn install
```

### 3. Update Your Workflow

| **Old (npm)**            | **New (Yarn)**  |
| ------------------------ | --------------- |
| `npm install`            | `yarn install`  |
| `npm test`               | `yarn test`     |
| `npm run build`          | `yarn build`    |
| `npm run commit`         | `yarn commit`   |
| `npm run lint-fix`       | `yarn lint-fix` |
| `npx prettier --write .` | `make format`   |

### 4. Make Commands Still Work

All `make` commands continue to work exactly as before:

- `make build` - Build all modules
- `make test` - Run all tests
- `make commit` - Create conventional commits
- `make deploy` - Deploy to AWS

## 🔍 What Changed

### Package Manager

- **Before**: npm with `package-lock.json`
- **After**: Yarn 4.12.0 with `yarn.lock`

### Security Scanning

- **Before**: `npm audit` (showed bundled dependency warnings)
- **After**: `yarn npm audit --severity moderate` (cleaner output, proper
  suppression)

### Workspace Management

- **Before**: npm workspaces
- **After**: Yarn workspaces (better performance and reliability)

### Clean Commands

- **Before**: Deleted entire `lib/` directories (including source files!)
- **After**: Only removes compiled `.js` and `.d.ts` files, preserves TypeScript
  source

## 🛠️ For CI/CD Pipelines

Update your CI/CD scripts:

```yaml
# Before
- name: Install dependencies
  run: npm ci

- name: Build
  run: npm run build

- name: Test
  run: npm test

# After
- name: Install dependencies
  run: yarn install --immutable

- name: Build
  run: yarn build

- name: Test
  run: yarn test
```

## 🐳 For Docker

Update your Dockerfiles:

```dockerfile
# Before
COPY package*.json ./
RUN npm ci --only=production

# After
COPY package.json yarn.lock ./
RUN corepack enable && yarn install --immutable --production
```

## ❓ Troubleshooting

### "yarn: command not found"

```bash
# Install Yarn
corepack enable
# or
npm install -g yarn
```

### "Cannot find module" errors

```bash
# Clean install
rm -rf node_modules .yarn/cache
yarn install
```

### Build failures after migration

```bash
# Ensure all workspaces are built
yarn build
```

### Git conflicts with lock files

```bash
# Remove old lock file
rm package-lock.json
git add package-lock.json

# Commit yarn.lock
git add yarn.lock
git commit -m "chore: migrate to yarn 4.12.0"
```

## 🔄 Rollback (if needed)

If you need to temporarily rollback to npm:

```bash
# Remove Yarn artifacts
rm -rf node_modules yarn.lock .yarn

# Reinstall with npm
npm install
```

**Note**: This is not recommended as the project configuration is now optimized
for Yarn.

## 📚 Learn More

- [Yarn 4 Documentation](https://yarnpkg.com/)
- [Yarn Workspaces](https://yarnpkg.com/features/workspaces)
- [Migration from npm](https://yarnpkg.com/getting-started/migration)

## 🆘 Need Help?

1. Check this migration guide
2. Review the updated [README.md](README.md)
3. Create an issue in the repository with the "yarn-migration" label
