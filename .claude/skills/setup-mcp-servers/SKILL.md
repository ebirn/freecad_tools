---
name: setup-mcp-servers
description: Configure the Context7, GitHub, and FreeCAD MCP servers for Claude Code and/or OpenCode. Use when the user asks to set up, install, fix, or check MCP servers/integrations for documentation lookup (Context7), GitHub, or FreeCAD control, in either tool.
---

# Setup MCP Servers (Context7, GitHub, FreeCAD)

This skill configures three MCP servers:

1. **Context7** — up-to-date library/framework documentation lookups.
2. **GitHub** — repo/issue/PR operations via the GitHub MCP server.
3. **FreeCAD** — live control of a running FreeCAD instance (documents, objects,
   screenshots, FEM) via `neka-nat/freecad-mcp`.

Two clients are supported: **Claude Code** (CLI-managed config) and **OpenCode**
(JSON config file). Ask the user which one they want configured if it's not
obvious from context, or do both if asked.

For each server, check current state first before adding anything — do not
duplicate existing entries.

---

## Claude Code

Check existing servers: `claude mcp list`.

Prefer user scope (`-s user`) for these three servers since they are
general-purpose tools, not project-specific, unless the user asks for project
scope (`-s project`, written to `.mcp.json`).

### 1. Context7

Requires `npx` (Node.js) on PATH.

```bash
claude mcp add -s user context7 -- npx -y @upstash/context7-mcp
```

If the user has a Context7 API key (higher rate limits), add it as an env var:

```bash
claude mcp add -s user context7 --env CONTEXT7_API_KEY=<key> -- npx -y @upstash/context7-mcp
```

Verify: `claude mcp get context7`.

### 2. GitHub

Two supported options — prefer the hosted remote server (no local install/Docker
needed):

**Option A: Hosted remote (recommended)**

```bash
claude mcp add -s user --transport http github https://api.githubcopilot.com/mcp/
```

On first use, Claude Code will prompt an OAuth-style browser login to authorize
GitHub access. Confirm with the user before running this if they haven't already
authenticated `gh`/GitHub with this tool.

**Option B: Local Docker server**

Only use if the user prefers a local server or hosted access is unavailable.
Requires Docker and a GitHub Personal Access Token.

```bash
claude mcp add -s user github \
  --env GITHUB_PERSONAL_ACCESS_TOKEN=<token> \
  -- docker run -i --rm -e GITHUB_PERSONAL_ACCESS_TOKEN ghcr.io/github/github-mcp-server
```

Never print or commit the token. Ask the user to supply it interactively or via
an existing env var reference rather than typing it in chat.

Verify: `claude mcp get github`.

### 3. FreeCAD (neka-nat/freecad-mcp)

See [FreeCAD addon setup](#freecad-addon-setup-both-clients) below first, then
register the MCP server:

```bash
claude mcp add -s user freecad -- uvx freecad-mcp
```

To reduce token usage (text-only feedback, no screenshots):

```bash
claude mcp add -s user freecad -- uvx freecad-mcp --only-text-feedback
```

Verify: `claude mcp get freecad`.

### Final check (Claude Code)

Run `claude mcp list` and confirm `context7`, `github`, and `freecad` all show as
connected. If `freecad` fails to connect, the most common cause is the RPC server
not running inside FreeCAD yet.

---

## OpenCode

OpenCode has no non-interactive `mcp add` CLI (it's a TUI prompt), so configure
servers by editing JSON config directly under the `mcp` key:

- Global config: `~/.config/opencode/opencode.jsonc`
- Project config: `opencode.json` / `opencode.jsonc` in the project root (merges
  over global)

Use the global config for these general-purpose servers unless the user asks for
project scope. Read the existing file first (it may just contain `{"$schema":
"https://opencode.ai/config.json"}`) and merge — don't overwrite other keys.

### 1. Context7

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": {
      "type": "local",
      "command": ["npx", "-y", "@upstash/context7-mcp"],
      "enabled": true
    }
  }
}
```

With an API key:

```jsonc
{
  "mcp": {
    "context7": {
      "type": "local",
      "command": ["npx", "-y", "@upstash/context7-mcp"],
      "environment": { "CONTEXT7_API_KEY": "<key>" },
      "enabled": true
    }
  }
}
```

### 2. GitHub

Hosted remote server, OAuth-based:

```jsonc
{
  "mcp": {
    "github": {
      "type": "remote",
      "url": "https://api.githubcopilot.com/mcp/",
      "enabled": true
    }
  }
}
```

After adding, authenticate with:

```bash
opencode mcp auth github
```

If the user prefers a local Docker server instead, use a `local` entry:

```jsonc
{
  "mcp": {
    "github": {
      "type": "local",
      "command": ["docker", "run", "-i", "--rm", "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
                   "ghcr.io/github/github-mcp-server"],
      "environment": { "GITHUB_PERSONAL_ACCESS_TOKEN": "<token>" },
      "enabled": true
    }
  }
}
```

Never print or commit the token.

### 3. FreeCAD (neka-nat/freecad-mcp)

See [FreeCAD addon setup](#freecad-addon-setup-both-clients) below first, then
add to config:

```jsonc
{
  "mcp": {
    "freecad": {
      "type": "local",
      "command": ["uvx", "freecad-mcp"],
      "enabled": true
    }
  }
}
```

For text-only feedback:

```jsonc
{
  "mcp": {
    "freecad": {
      "type": "local",
      "command": ["uvx", "freecad-mcp", "--only-text-feedback"],
      "enabled": true
    }
  }
}
```

### Final check (OpenCode)

Run `opencode mcp list` and confirm `context7`, `github`, and `freecad` show as
connected/enabled.

---

## FreeCAD addon setup (both clients)

The FreeCAD MCP server needs an addon installed *inside* FreeCAD that runs an RPC
server — this is independent of which client (Claude Code or OpenCode) connects
to it, and only needs to be done once per FreeCAD installation. Requires
`uv`/`uvx` on PATH.

Determine the FreeCAD `Mod/` directory for the user's OS/version, e.g. on macOS
with FreeCAD 1.1:

```bash
~/Library/Application\ Support/FreeCAD/v1-1/Mod/
```

(macOS FreeCAD 1.0: `v1-0` instead of `v1-1`. Linux: `~/.FreeCAD/Mod/`,
`~/.local/share/FreeCAD/Mod`, or `~/.local/share/FreeCAD/v1-1/Mod/` depending on
distro/install method. Windows: `%APPDATA%\FreeCAD\Mod\`.)

Clone the repo and copy the addon directory in:

```bash
git clone https://github.com/neka-nat/freecad-mcp.git /tmp/freecad-mcp
mkdir -p "<Mod-dir>"
cp -r /tmp/freecad-mcp/addon/FreeCADMCP "<Mod-dir>/"
```

Then tell the user to:
1. Restart FreeCAD.
2. Switch to the **MCP Addon** workbench.
3. Run **Start RPC Server** (or enable **Auto-Start Server** in the FreeCAD MCP
   menu so it starts automatically on launch).

The FreeCAD application with the addon's RPC server running must be active for
the `freecad` MCP tools to work — this is a live-control integration, separate
from this repo's headless `freecadcmd`-based export pipeline.
