# WordPress kit

Additive overlay for a WordPress site so every project gets WP-CLI/PHPCS wiring, a site-safety skill across all three agents, and an MCP example that uses SecretRef placeholders.

This kit does not scaffold WordPress. It does not install WP-CLI, PHPCS, or a plugin. It copies the overlay into a tree that already has `wp-load.php` or `wp-config.php`.

Install `kits/base` (or `python forge.py init`) first when the repo should speak the full agent contract.

## What lands

| Path | Role |
| ---- | ---- |
| `docs/wordpress-agent-tooling.md` | Bind WP-CLI, PHPCS WordPress-Extra, and MCP |
| `.agents/skills/wordpress-site-safety/SKILL.md` | Antigravity (`agy`) skill copy |
| `.claude/skills/wordpress-site-safety/SKILL.md` | Claude Code (`claude`) skill copy |
| `.codex/skills/wordpress-site-safety/SKILL.md` | OpenAI Codex (`codex`) copy + `openai.yaml` |
| `phpcs.xml.dist` | WordPress-Extra ruleset |
| `tools/phpcs/composer.json` | Isolated WPCS toolchain (`composer install`) |
| `scripts/hooks/wordpress-phpcs-pre-push.sh` | Pre-push check |
| `mcp.wordpress.example.json` | MCP fragment with `${WP_API_*}` placeholders |

## Install

```powershell
python forge.py kit /path/to/wordpress-project wordpress
python forge.py kit /path/to/wordpress-project wordpress --dry-run
```

```bash
kits/wordpress/scripts/install.sh /path/to/wordpress-project
kits/wordpress/scripts/install.sh /path/to/wordpress-project --dry-run
kits/wordpress/scripts/doctor.sh /path/to/wordpress-project
```

The target may be the WordPress root or a monorepo whose `website/`, `wordpress/`, or `wp/` child contains `wp-load.php` / `wp-config.php`.

## Operator globals

```bash
# user-scoped WP-CLI; do not drop an unverified PHAR into the repo
wp --info
cd /path/to/project/tools/phpcs && composer install
```

MCP application passwords stay in secret management as SecretRefs. PHP-execution and file abilities stay off outside verified backups.
