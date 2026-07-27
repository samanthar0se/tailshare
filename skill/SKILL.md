---
name: share
description: Put an HTML file in front of the user on their actual screen. Use whenever you have built or are about to build an HTML prototype, mockup, chart, report, or any standalone page the user needs to look at — instead of giving them a file path or a file:// link. Also use when the user says "show me", "let me see it", "open that", or reports that a link you gave them does not work.
---

# Share

The user drives this machine remotely over Tailscale. **A path on disk is useless to them** — `C:\git\foo\index.html` and `file:///C:/...` both resolve on your box, not on their screen. Anything they need to *look at* must be served over the tailnet and opened in the preview pane.

A share server already runs for exactly this. Use it.

## The loop

1. **Write the file** into `C:\git\.share\`.
   - Single page → `C:\git\.share\<slug>.html`
   - Multi-file (CSS/JS/assets) → `C:\git\.share\<slug>\index.html` and friends. Relative URLs resolve correctly, so build it normally.
   - `<slug>` is kebab-case and descriptive: `pricing-table-v2`, not `test` or `index`.
2. **Check for a live tab** with `mcp__t3-code__preview_status`. If `tabId` is `null` the pane was closed — go to step 3 and skip the navigate, because `preview_navigate` has no tab to drive and will hang for 15s before failing.
3. **Open or navigate**, whichever applies:
   - No tab (`tabId: null`) → `mcp__t3-code__preview_open` with the URL and `show: true`. This creates the tab and loads the page in one call.
   - Tab exists → `mcp__t3-code__preview_navigate` to `http://clanker.tail7c7e46.ts.net:8000/<slug>.html`, then `preview_open` with `show: true` if `visible` is `false`.
4. **Tell the user the URL** in your reply as well, so they can open it in a real browser tab or on their phone. Same tailnet, same URL.

## Rules

1. **Never hand over a bare file path or `file://` URL** as the way to view something. That is the failure this skill exists to prevent.
2. **Set the viewport before judging layout.** The pane defaults to `fill`, which produces odd geometry like 539×1539. Call `mcp__t3-code__preview_resize` with `mode: "freeform", width: 1280, height: 800` for a desktop canvas, or a device `preset` when the point is mobile layout. Do this *before* you screenshot and conclude something looks wrong.
3. **Re-navigate after every edit.** The server sends `no-store`, so a plain re-navigate always shows current bytes. Never tell the user to hard-refresh.
4. **Verify, don't assume.** After navigating, check `preview_status` — a matching `title` means it rendered. Use `mcp__t3-code__preview_snapshot` when you need to see it yourself. `visibleText` and `consoleEntries` in that snapshot are how you catch a blank page or a JS error.
5. **Keep the directory browsable.** `http://clanker.tail7c7e46.ts.net:8000/` lists everything shared so far. Don't clutter it with scratch files, and delete probes when done.

## If it does not load

Work down this list; it is ordered by how often each is the cause.

1. **Timed out after 15s?** Almost always a closed tab, not a broken server. Check `preview_status` for `tabId: null` and `preview_open` a fresh one. Cross-check `server.log` — a logged `200` proves the serving half is fine and the problem is the pane.
2. **Server down.** `Get-ScheduledTask -TaskName ShareServer` → if not `Running`, `Start-ScheduledTask -TaskName ShareServer`.
3. **Check the log.** `C:\git\tailshare\server.log` shows every request and the bind address it chose.
4. **Tailscale IP changed.** The URL host is baked into this skill. Confirm with
   `& 'C:\Program Files\Tailscale\tailscale.exe' status --json | ConvertFrom-Json | % { $_.Self.DNSName }`
   and update this file if it differs from `clanker.tail7c7e46.ts.net`.
5. **Bound to loopback.** If someone changed the server to bind `127.0.0.1`, it will pass a local `curl` and still be invisible to the user. The preview pane rewrites `localhost:PORT` to `<magicdns-name>:PORT` and has the *client* fetch directly — there is no proxy. It must bind the Tailscale IP.

## Layout

- `C:\git\.share\` — served root, world-readable to your tailnet. Not in the repo; it is scratch output.
- `C:\git\tailshare\` — the repo: server, installer, and this skill
- `C:\git\tailshare\server.log` — request log
- `~\.claude\skills\share` — a **junction** to `C:\git\tailshare\skill`. Edit the file in the repo; there is only one copy.
