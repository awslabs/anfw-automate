# Semantic Versioning & Releases

This project uses **semantic-release** to calculate versions and generate
releases from conventional commit messages. Releases are cut by running
`yarn release` from `main`; no CI workflow runs it.

## How It Works

### Automatic Version Bumping

- **feat**: Minor version bump (2.1.0 → 2.2.0)
- **fix**: Patch version bump (2.1.0 → 2.1.1)
- **perf**: Patch version bump (2.1.0 → 2.1.1)
- **BREAKING CHANGE**: Major version bump (2.1.0 → 3.0.0)

### Release Branches

- **main**: Production releases (2.1.0, 2.2.0, etc.)
- **dev**: Beta releases (2.2.0-beta.1, 2.2.0-beta.2, etc.)

### What Gets Automated

1. **Version calculation** from commit messages
2. **CHANGELOG.md generation** with release notes
3. **Package.json updates** across all workspaces
4. **Git tags** for releases
5. **GitHub releases** with release notes

## Usage

### Testing Releases Locally

```bash
# Dry run to see what would happen
yarn release:dry-run
```

### Cutting a Release

```bash
# From an up-to-date main, with a token that can push tags and create releases
git checkout main && git pull
GITHUB_TOKEN=<token> yarn release
```

### Workspace Version Sync

```bash
# Sync versions across all workspaces
yarn version:sync
```

## Commit Message Examples

### Minor Release (feat)

```bash
git commit -m "feat(app): add new firewall rule validation"
# Results in: 2.1.0 → 2.2.0
```

### Patch Release (fix)

```bash
git commit -m "fix(firewall): resolve routing table race condition"
# Results in: 2.1.0 → 2.1.1
```

### Major Release (BREAKING CHANGE)

```bash
git commit -m "feat(app): redesign API structure

BREAKING CHANGE: API endpoints have changed structure"
# Results in: 2.1.0 → 3.0.0
```

### No Release

```bash
git commit -m "docs: update README"
git commit -m "chore: update dependencies"
git commit -m "ci: fix workflow"
# No version bump
```

## Release Process

1. **Merge to main**: Merge the PR once CI is green
2. **Dry run**: `yarn release:dry-run` to preview the version and notes
3. **Release**: `GITHUB_TOKEN=<token> yarn release` from `main`
4. **Version bump**: Calculates the new version from commits
5. **Update files**: Updates package.json files and CHANGELOG.md, commits them
6. **Create release**: Tags and creates the GitHub release

Deployment is separate: the app CodePipeline deploys from the repository and
runs the integration tests as its final wave.

## Monorepo Handling

All workspace packages maintain the same version:

- `app/package.json`
- `foundational/package.json`
- `shared/package.json`

The version sync script ensures consistency across all packages.

## Configuration Files

- **`.releaserc.json`**: Semantic-release configuration
- **`scripts/sync-versions.js`**: Workspace version synchronization

## Troubleshooting

### No Release Created

- Check commit messages follow conventional format
- Ensure you are on main or dev and up to date with the remote
- Check `GITHUB_TOKEN` is set and can push tags and create releases

### Version Sync Issues

```bash
# Manually sync versions if needed
yarn version:sync
```

### Rollback Release

```bash
# Revert the release commit
git revert HEAD
git push origin main
```

## Best Practices

1. **Use conventional commits** - Required for automatic versioning
2. **Test with dry-run** - Always test before releasing
3. **Review CHANGELOG** - Check generated release notes
4. **Keep workspaces in sync** - Use version sync script

## Examples

### Feature Development Workflow

```bash
# 1. Create feature branch
git checkout -b feature/add-validation

# 2. Make changes and commit
git add .
git commit -m "feat(app): add rule validation system"

# 3. Push and create PR
git push origin feature/add-validation

# 4. Merge to main, then run `yarn release` from main
# Result: Version bumped to 2.2.0, CHANGELOG updated, GitHub release created
```

### Hotfix Workflow

```bash
# 1. Create hotfix branch
git checkout -b hotfix/critical-fix

# 2. Fix and commit
git add .
git commit -m "fix(foundational): resolve critical security issue"

# 3. Merge to main, then run `yarn release` → patch release
# Result: Version bumped to 2.1.1, hotfix documented
```
