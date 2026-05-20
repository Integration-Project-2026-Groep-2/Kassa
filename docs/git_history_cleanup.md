# Git History Cleanup (remove sensitive files)

If you must remove a file from repository history (e.g. `coverage.xml` or leaked `.env`):

1. Install `git filter-repo` (preferred) or use BFG Repo-Cleaner.
2. Clone a mirror of the repo:

```bash
git clone --mirror https://github.com/Integration-Project-2026-Groep-2/Kassa.git
cd Kassa.git
```

3. Remove paths:

```bash
git filter-repo --path path/to/secret.file --invert-paths
```

4. Push changes (force):

```bash
git push --force
```

5. Notify collaborators and rotate any secrets that were removed.
