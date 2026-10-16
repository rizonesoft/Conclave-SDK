# Plugins

Standalone agent plugins that are not part of any kit: a Claude Code plugin, a Codex plugin or an Antigravity plugin bundle that you load on its own, by path or from a marketplace. `forge.py` never copies anything from here into a project.

A plugin that only makes sense together with a kit lives in that kit instead (`kits/<kit>/plugins/`), so choosing the kit is what brings it in.

Give each plugin its own folder, named for its capability, with its manifest and a README that says which agent loads it and how.
