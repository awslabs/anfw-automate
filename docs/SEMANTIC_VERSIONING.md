# Semantic Versioning & Automated Releases

This project uses **semantic-release** to automatically manage versions and
releases based on conventional commit messages.

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

### Manual Release (if needed)

```bash
# Trigger release manually
yarn release
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

### Automatic (Recommended)

1. **Merge to main**: Push/merge commits to main branch
2. **GitHub Actions**: Automatically runs release workflow
3. **Version bump**: Calculates new version from commits
4. **Update files**: Updates package.json, CHANGELOG.md
5. **Create release**: Tags and creates GitHub release

### Manual Override

If you need to skip automatic release:

```bash
git commit -m "fix(app): urgent hotfix [skip ci]"
```

## Monorepo Handling

All workspace packages maintain the same version:

- `app/package.json`
- `firewall/package.json`
- `vpc/package.json`
- `shared/package.json`

The version sync script ensures consistency across all packages.

## Configuration Files

- **`.releaserc.json`**: Semantic-release configuration
- **`scripts/sync-versions.js`**: Workspace version synchronization
- **`.github/workflows/release.yml`**: GitHub Actions release workflow

## Troubleshooting

### Release Not Triggered

- Check commit messages follow conventional format
- Ensure commits are on main or dev branch
- Verify GitHub Actions workflow is enabled

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
4. **Monitor releases** - Watch GitHub Actions for issues
5. **Keep workspaces in sync** - Use version sync script

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

# 4. Merge to main → Automatic release!
# Result: Version bumped to 2.2.0, CHANGELOG updated, GitHub release created
```

### Hotfix Workflow

```bash
# 1. Create hotfix branch
git checkout -b hotfix/critical-fix

# 2. Fix and commit
git add .
git commit -m "fix(firewall): resolve critical security issue"

# 3. Merge to main → Automatic patch release!
# Result: Version bumped to 2.1.1, hotfix documented
```
