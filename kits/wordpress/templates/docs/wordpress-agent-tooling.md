# WordPress agent tooling

Every WordPress project Conclave starts or adopts gets this overlay. jmr-online (`website/`) is the reference.

## Bind one site first

Discover the canonical URL, filesystem owner, PHP/WordPress versions, and transport (local files, WP-CLI, SSH, REST, MCP) before changing anything. Local, staging, production, and multisite scopes stay distinct. A write that does not name the site is refused.

## WP-CLI

User-scoped. `wp --info` then read-only identity commands (`wp core version`, `wp site list`) before any write. Do not drop an unverified PHAR into the repository.

## PHPCS

`phpcs.xml.dist` is WordPress-Extra. The toolchain lives in `tools/phpcs/` so the site's own `composer.json` is not polluted. After `composer install` in that directory:

```bash
tools/phpcs/vendor/bin/phpcs
```

`scripts/hooks/wordpress-phpcs-pre-push.sh` is the pre-push snippet. Wire it from the project's hook. A missing binary is SKIPPED, not a silent pass.

## MCP

`mcp.wordpress.example.json` uses `${WP_API_URL}`, `${WP_API_USERNAME}`, and `${WP_API_PASSWORD}` only. Merge into `.mcp.json` by hand. Application passwords are SecretRefs. The official MCP Adapter is the default. Novamira bundles that adapter; deactivate any standalone copy. Novamira's own PHP-execution and file abilities stay disabled outside dev/staging with verified backups. They are blanket-authority capabilities.
