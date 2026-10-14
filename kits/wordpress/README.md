# WordPress kit

Additive overlay for a WordPress site so every project gets WP-CLI/PHPCS wiring, a site-safety skill across Gemini (`.agents/`), Claude (`.claude/`), and Codex (`.codex/`), and an MCP example that uses SecretRef placeholders.

This kit does not scaffold WordPress. It does not install WP-CLI, PHPCS, or a plugin. It copies the overlay into a tree that already has `wp-load.php` or `wp-config.php`.

Install `kits/base` (or `python forge.py init`) first when the repo should speak the full agent contract.

## What lands

| Path | Role |
| ---- | ---- |
| `docs/wordpress-agent-tooling.md` | How to bind WP-CLI, PHPCS WordPress-Extra, and MCP to one site |
| `.agents/skills/wordpress-site-safety/SKILL.md` | Gemini / Antigravity (`agy`) skill copy |
| `.claude/skills/wordpress-site-safety/SKILL.md` | Claude Code (`claude`) skill copy |
| `.codex/skills/wordpress-site-safety/SKILL.md` | OpenAI Codex (`codex`) skill copy plus `agents/openai.yaml` |
| `phpcs.xml.dist` | WordPress-Extra ruleset configuration |
| `tools/phpcs/composer.json` | Isolated WPCS toolchain (`composer install` is operator-approved) |
| `scripts/hooks/wordpress-phpcs-pre-push.sh` | Pre-push check for staged PHP files |
| `mcp.wordpress.example.json` | MCP adapter fragment with `${WP_API_*}` placeholders, never literals |

## Install

```powershell
python forge.py kit /path/to/wordpress-project wordpress [--agent all|gemini|claude|codex] [--dry-run]
python forge.py doctor /path/to/wordpress-project wordpress
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
