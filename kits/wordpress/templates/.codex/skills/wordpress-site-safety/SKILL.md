---
name: wordpress-site-safety
description: "Bind WordPress work to one named site. Read-only first. Approval-gated writes. SecretRef credentials. Use when editing a WordPress tree, running WP-CLI, or calling a WordPress MCP adapter."
---

# WordPress site safety

1. Name the site and environment (local, staging, production, or a specific multisite blog). Stop if you cannot.
2. Run read-only identity commands first (`wp --info`, `wp core version`).
3. Treat plugin/theme/content/user/database/filesystem/deployment writes as approval-gated. Production is a separate gate.
4. Credentials are SecretRefs. Never paste an application password into `.mcp.json`.
5. Official MCP Adapter is the default. Novamira bundles it; deactivate a standalone copy. Leave Novamira PHP-execution and file abilities disabled outside verified backups.
6. PHPCS WordPress-Extra via `tools/phpcs/` is the style gate when that toolchain is installed.
