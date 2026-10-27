# Legacy Website to Static

[简体中文](README.md) | English

`legacy-site-to-static` is a Skill for AI Agents that helps migrate aging corporate websites and product catalogs from PHP, ASP, or an older CMS to maintainable static websites.

It brings together content recovery, local editing, multilingual content, FTP publishing, traffic routing, and rollback procedures from a real migration. It includes three read-only checking tools and suits projects that want to retain their existing content, visual style, and usable hosting.

**The Agent must implement any editor, translation integration, or FTP publisher for the specific project. This repository provides a workflow and checking scripts, rather than a ready-to-install universal admin application.**

The core workflow and scripts do not depend on a particular model API. The Agent needs access to local files and the ability to run scripts when needed. Skill discovery, installation directories, and invocation syntax depend on the Agent tool you use.

## Installation and usage

Download the repository or clone it locally:

```bash
git clone https://github.com/reinmj/skills.git
```

If your Agent supports importing Skills, import the entire `skills/legacy-site-to-static` folder into a supported location, preserving its internal structure. Follow your Agent tool's installation instructions.

You can also ask the Agent to read the local `SKILL.md` directly. Replace the path below with its actual absolute path:

```text
Read /path/to/skills/skills/legacy-site-to-static/SKILL.md
and follow its workflow to migrate this legacy website.
Source code: [source location].
Database backup: [SQL file or archive location].
Images and web files: [backup location].
Start with a read-only assessment of content completeness,
dynamic features, and the deployment chain.
Then build a locally reviewable static version,
preserving the existing content and visual style.
```

Check for an existing Skill with the same name before installing another copy. Remote uploads and production routing changes must stay within the current project's authorization.

## Suitable projects

Company profiles, product catalogs, news, case studies, download centers, and multilingual informational pages are good candidates for assessment. Available source code, database backups, and media files determine the recovery and generation approach.

Authentication, orders, payments, member data, and live inventory require a backend. Separate informational pages from dynamic business features, then decide whether to retain, migrate, or rebuild the backend. Contact forms also need a working receiving service.

## Migration workflow

1. Identify the authoritative source for text, images, attachments, and each language.
2. Generate a local static website with traceable content IDs, routes, and visual styling.
3. Implement local editing, translation drafts, human review, and versioned backups as needed.
4. Check the public directory, keeping editing data, secrets, and legacy server code outside public access.
5. Prepare backups, test publishing, traffic cutover, and rollback within the authorized scope.
6. Verify the actual domain, origin, content version, images, and key interactions, then document routine updates.

A completed FTP upload, a running host, disabled script execution, proxy access, and production routing each need separate verification. A physical directory named `preview` may already serve the production website.

## Repository structure

```text
skills/legacy-site-to-static/
  SKILL.md                    Workflow and scope
  agents/openai.yaml          Optional host UI metadata
  assets/                     Generic project configuration example
  references/                 Recovery, editing, publishing, and checking guides
  scripts/                    Three checking tools and a shared module
tests/run_tests.py             Regression checks using synthetic fixtures
docs/wechat-article.md         WeChat introduction article in Chinese
docs/x-posts.txt               X post and thread in Chinese
```

## Run the checking tools directly

The scripts require Python 3.9 or later and use only its standard library. Run these examples from the repository root, replace the paths with your project's locations, and keep reports outside both the source materials and public website directory.

```bash
# Inventory directory or ZIP metadata without executing or extracting old code
python3 skills/legacy-site-to-static/scripts/inventory_sources.py \
  /private/source /private/web-backup.zip \
  --out /private/reports/inventory.json

# Check the public release using a policy configured for the current project
python3 skills/legacy-site-to-static/scripts/check_release.py \
  /project/public --mode formal --policy /private/project.json \
  --out /private/reports/release.json

# Check explicitly specified URLs without automatically following redirects
python3 skills/legacy-site-to-static/scripts/probe_routes.py \
  https://www.example.invalid/ \
  --out /private/reports/http.json
```

See each script's `--help` and the [checking tool guide](skills/legacy-site-to-static/references/checks.md), currently written in Chinese, for the full options. The example domain is intentionally nonfunctional and must be replaced.

The inventory tool does not parse SQL contents. The release checker examines local references, path casing, file manifests, selected sensitive-file patterns, and declared project rules. The HTTP tool checks response status and bounded reads. These tools do not execute browser JavaScript or replace content review, image decoding, business-function testing, or a full security audit.

## Maintenance and validation

```bash
python3 -B tests/run_tests.py
```

Regression checks use temporary synthetic fixtures and local HTTP servers. When `openssl` is available, they also verify rejection of an untrusted HTTPS certificate. The original version passed on macOS with Python 3.9; Windows execution still requires separate validation.

Static delivery reduces exposure to public server-side code. Hosting, access accounts, proxies, and local management tools still need maintenance. Roll back using a verified static release instead of re-enabling an unsafe legacy backend.

This repository excludes the original project's source code, databases, media, access credentials, and deployment addresses. Keep actual project materials, complete editing backups, and checking reports outside this repository.
