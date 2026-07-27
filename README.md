# tailshare

Puts HTML prototypes in front of a user who is driving this machine remotely
over Tailscale.

The problem: an agent builds `C:\git\foo\index.html` and hands over the path.
The user is on another computer — that path, and `file:///C:/...`, resolve on
the host and show them nothing. tailshare serves a directory over the tailnet so
the file becomes a URL the user's browser can actually load, then opens it in
t3code's preview pane.

## Why it binds to the Tailscale IP, not loopback

t3code's preview pane does **not** proxy. Given `localhost:8000` it rewrites the
host to `<magicdns-name>:8000` and the *client* fetches directly. A server bound
to `127.0.0.1` passes a local `curl` and is still invisible to the user — which
looks exactly like a broken preview.

`share_server.py` discovers the tailnet address from `tailscale status --json`
and retries for up to 10 minutes, so it survives starting before Tailscale is up
at logon.

## Install

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1
```

This junctions `skill\` into `~\.claude\skills\share` and registers a
`ShareServer` scheduled task that starts at logon, windowless. No elevation
needed — directory junctions and high ports are both unprivileged.

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall
```

## Layout

| Path | What |
|---|---|
| `share_server.py` | the server |
| `install.ps1` | install / uninstall |
| `skill\SKILL.md` | the agent-facing skill, junctioned into `~\.claude\skills\share` |
| `server.log` | request log (gitignored) |
| `C:\git\.share\` | served root — scratch output, deliberately outside this repo |

## Operating

```powershell
Get-ScheduledTask -TaskName ShareServer
Start-ScheduledTask -TaskName ShareServer
python share_server.py            # foreground instead, logs to console
```

## Notes

- Responses are `no-store`, and `If-Modified-Since` is stripped, so a file
  rewritten twice within the same second still serves fresh. Without that, mtime
  resolution produces a 304 and the user thinks their feedback was ignored.
- No auth. The tailnet ACL is the boundary; anything on the tailnet can read
  `C:\git\.share`. Don't put secrets there.
- The root URL renders a directory listing of everything shared so far.
- The skill is a junction, not a copy. Edit `skill\SKILL.md` in this repo.
