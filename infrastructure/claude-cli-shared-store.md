# Claude CLI — Shared Conversation Store (everywhere)

**Last Updated**: 2026-06-25
**Related Systems**: CT 124 (Claude AI), claude-dev, claude.home

## Summary
A small wrapper at `/usr/local/bin/claude` on **CT 124** makes the `claude` CLI always
run as user **`claudeai`** from **`/home/claudeai`**, regardless of who invokes it
(Proxmox console / root SSH / claudeai SSH / browser console). Result: every entry point
shares one conversation store, so any chat is visible and resumable from anywhere.

## Problem / Goal
The Claude CLI files conversations under `~/.claude/projects/<cwd-slug>/` — keyed by the
Unix user's `$HOME` **and** the directory it was launched from. claude-dev runs as
`claudeai` with cwd pinned to `/home/claudeai`, and the browser console (`claude.home`,
ttyd) runs `su - claudeai -c claude` — so both already share
`/home/claudeai/.claude/projects/-home-claudeai/`. The **Proxmox text console auto-logs in
as `root`**, whose `~/.claude` is a separate, empty store, so conversations started in
claude-dev were invisible there. Goal: same conversations everywhere.

## Solution
Shadow `claude` on the system `PATH` with a wrapper that re-execs the real binary as
`claudeai`. claude-dev is unaffected — it invokes the binary by absolute path
(`CLAUDE_BIN=/home/claudeai/.local/bin/claude`), never via `PATH`. The `claudeai` user's
own shell also bypasses the wrapper (its `~/.local/bin` precedes `/usr/local/bin` on
`PATH`), so the wrapper only ever intercepts root / other users.

## Implementation Details

### File: `/usr/local/bin/claude` (root-owned, mode 0755)
```sh
#!/bin/sh
# Always launch the real Claude CLI as user `claudeai` from /home/claudeai so every
# entry point shares ONE store at ~/.claude/projects/-home-claudeai/.
# claude-dev is unaffected (it invokes CLAUDE_BIN by absolute path).
REAL=/home/claudeai/.local/bin/claude
if [ "$(id -un)" = claudeai ]; then
  exec "$REAL" "$@"
else
  exec sudo -iu claudeai -- "$REAL" "$@"
fi
```
- Passwordless re-exec relies on existing `/etc/sudoers.d/claudeai` (`NOPASSWD: ALL`).
- `sudo -iu` sets `HOME`/cwd to `/home/claudeai`; MOTD is suppressed when a command is
  passed, and the controlling TTY / stdin / args are preserved (TUI works).

### Usage (from the Proxmox console or anywhere)
```sh
claude --resume                 # picker lists all conversations
claude --resume <session-id>    # jump straight to one
claude --continue               # resume the most recent
```

## Verification
```sh
# As root, the wrapper must resolve to claudeai @ /home/claudeai:
sudo sh -c 'sudo -iu claudeai -- sh -c "echo \$(id -un) \$HOME \$(pwd)"'
#   → claudeai /home/claudeai /home/claudeai
# Conversations now visible from the console:
ls -lt /home/claudeai/.claude/projects/-home-claudeai/*.jsonl | head
```

## Troubleshooting
- **Revert completely**: `sudo rm /usr/local/bin/claude` — restores prior behavior exactly.
  This is a standalone file: NOT part of the claude-dev repo, its build/deploy, or git, and
  it persists only on CT 124.
- **Do not drive the same conversation from two live places at once** (e.g. a claude-dev
  browser tab *and* the console on the same session id). claude-dev's single-writer lock
  does not extend to an external CLI process, and the `.jsonl` has no file lock — concurrent
  writers can corrupt a turn. Close the other side first, or branch a safe copy with
  `claude --resume <id> --fork-session`.
- **Need a directory-specific (non-pooled) session** from the console: call the real binary
  directly at `/home/claudeai/.local/bin/claude` instead of the wrapper.
