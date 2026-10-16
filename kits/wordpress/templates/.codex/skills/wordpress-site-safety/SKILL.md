---
name: wordpress-site-safety
description: "Bind WordPress work to one named site. Read-only first. Approval-gated writes. SecretRef credentials. Use when editing a WordPress tree, running WP-CLI, or calling a WordPress MCP adapter."
---

# WordPress site safety

1. Name the site and environment (local, staging, production, or a specific multisite blog); `.conclave/wordpress-site.json` pins the live one. Stop if you cannot.
2. Run read-only identity commands first (`wp --info`, `wp core version`).
3. Treat plugin/theme/content/user/database/filesystem/deployment writes as approval-gated. Production is a separate gate.
4. Credentials are SecretRefs. Never paste an application password into `.mcp.json`.
5. WordPress MCP comes from the host: on Pressable the official `mcp-adapter`, enabled with Pressable `toggle_site_wordpress_mcp`; on WordPress.com the WordPress.com connector, never `mcp-adapter`. Novamira is discontinued: never install it, and ask before removing it from a site that still has it.
6. PHPCS WordPress-Extra via `tools/phpcs/` is the style gate when that toolchain is installed.
