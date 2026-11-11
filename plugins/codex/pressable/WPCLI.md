# Reviewed WP-CLI access (0.2.1)

The plugin exposes 57 reviewed operations: 36 reads and 21 changes, through its existing six MCP tools and private Pressable tunnel.

New operations:
- run_site_wpcli_commands: preview and submit exactly one command for a numeric site ID.
- get_site_wordpress_operation: read status/output using exactly one job_id or operation_id.
- list_site_wordpress_operations: bounded history, maximum 50 entries per page.

Use describe_operation to see the exact provider schema and pluginPolicy.allowedSubcommands. Supported command families include media import, post and post-meta reads/updates, menu-item updates, widget updates, option reads/updates, theme mods, selected diagnostics and cache flushing. PHP eval, database SQL, arbitrary shell, remote-target overrides and credential operations are excluded. Command strings are bounded to 8192 characters and must omit the wp prefix. Quote literal HTML/JSON. Shell expansions, escapes, substitutions and chaining are rejected. URLs must have no credentials, query string or fragment; never submit signed URLs or secrets because Pressable logs commands in plaintext.

Example parameters (placeholders, not permission to execute):

```json
{"site_id":123,"commands":["media import https://example.com/certificate.pdf --title='Certificate' --porcelain"]}
```

After submission, preserve the job ID and poll it using the same site ID. The provider queue does not guarantee ordering between commands. Successful output may be truncated to 500 characters; use focused reads or Website Router for complete data and outcome verification. The plugin returns completion_verified=false on submission deliberately.

For footer work, locate the actual menu/widget/option/template/Elementor storage first. Preserve old values and confirm an appropriate database/site backup before preparing a change. The PDF must exist on the remote host or a reachable HTTPS URL; this operation does not transfer local files. Website Router SFTP can upload individual files within its current limits. No certificate or footer was changed while developing this extension.

References: [Pressable WP-CLI API](https://my.pressable.com/documentation/api/), [official MCP expansion](https://pressable.com/changelog/feature-release-major-expansion-for-pressable-mcp/), [WordPress media import](https://developer.wordpress.org/cli/commands/media/import/), [menu item update](https://developer.wordpress.org/cli/commands/menu/item/update/).
