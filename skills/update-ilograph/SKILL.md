---
name: update-ilograph
description: Updates an existing ilograph.yaml file to match the current state of a codebase
---

# Phase 1 - Determine code differences since last generation or update

Determine what has changed in the codebase since the last time the ilograph.yaml file was generated or updated.

## Find the difference using git (strongly preferred)

First, determine if git can be used to determine the differences in the codebase since last update. Use `git status` to determine if the current codebase is tracked using git. If it is, check the ilograph.yaml file for a commit hash. It will be somewhere in the file in this format:

```yaml
# PLEASE DO NOT REMOVE
# REPO URL: <repo url>
# COMMIT HASH: <commit hash>
```

Use `git rev-parse --short HEAD` to determine the *current* hash of the codebase.

See the code differences using `git diff <old-commit-hash>..<current-commit-hash>`

## Find the differences without using git (backup strategy)

If the current codebase is not tracked using git, changes to the codebase since last generation or update will have to be inferred. Analyze the codebase anew as specified in the "Phase 1" of the `generate-ilograph` skill. Compare this analysis to what is in the existing `ilograph.yaml` file. Try to determine what logic or structural changes may have occurred in the codebase.

# Phase 2 - Update ilograph.yaml

Update the ilograph.yaml file to account for the code changes. Make sure the sequence flow steps account for any new or changed logic. Also update any resource descriptions, or even add new resources, if the code changes necessitate it. When updating, be sure all the conventions outlined in the `generate-ilograph` skill are followed.

For small updates, it is unlikely that any perspectives will need to be added or removed outright. This may be the case for larger updates; ask the user before adding or removing any perspectives.

Update the code citations to match the new version. Check every citation and update the line numbers where needed. If the citations have links, update the `<commit hash>` values in the links.

Also update the `<commit hash>` on the `# COMMIT HASH:` line in the yaml file, if present.

Before finishing, complete the review checklist specified in "Phase 3" of the `generate-ilograph` skill.
