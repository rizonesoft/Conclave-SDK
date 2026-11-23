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
7. On an Elementor site behind a page cache, end every plugin, theme or Elementor change (activate, deactivate, update, a cache clear, a saved component or global class) with `python3 scripts/elementor-cache.py check`: Elementor deletes its stylesheets and cached HTML goes on naming them, so visitors get unstyled pages while an editor sees nothing wrong. If `status` reports the purge plugin absent, purge the page cache first, and offer the plugin (`wordpress-connect` step 6).
8. A dashboard login ticket link (`?conclave_ticket=...`) is a credential while it lives: never print, paste, or log it.
