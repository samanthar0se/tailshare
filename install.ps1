# Installs tailshare:
#   1. junctions the skill into global agent skill directories
#   2. registers the share server as a Scheduled Task that starts at logon
#
# Runs windowless via pythonw.exe. The server waits for Tailscale to hand out an
# IP, so it tolerates starting before Tailscale is up. No elevation required —
# directory junctions and high ports both work unprivileged.
#
#   Install:    powershell -ExecutionPolicy Bypass -File install.ps1
#   Uninstall:  powershell -ExecutionPolicy Bypass -File install.ps1 -Uninstall

param(
    [switch]$Uninstall,
    [string]$TaskName = "ShareServer",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$root      = Split-Path -Parent $MyInvocation.MyCommand.Path
$script    = Join-Path $root "share_server.py"
$log       = Join-Path $root "server.log"
$skillSrc  = Join-Path $root "skill"
$skillLinks = @(
    (Join-Path $env:USERPROFILE ".agents\skills\share"),
    (Join-Path $env:USERPROFILE ".pi\agent\skills\share"),
    (Join-Path $env:USERPROFILE ".codex\skills\share"),
    (Join-Path $env:USERPROFILE ".claude\skills\share")
)
$pythonw   = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\pythonw.exe"

if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -EA SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        "Removed scheduled task '$TaskName'."
    } else {
        "No scheduled task named '$TaskName'."
    }
    foreach ($skillLink in $skillLinks) {
        $existing = Get-Item $skillLink -EA SilentlyContinue
        if ($existing -and $existing.LinkType -eq "Junction") {
            # Remove the junction only. Never recurse here: on some PowerShell
            # versions that would delete through the link into the repo.
            [System.IO.Directory]::Delete($skillLink)
            "Removed skill junction: $skillLink"
        }
    }
    return
}

if (-not (Test-Path $pythonw)) { throw "pythonw.exe not found at $pythonw" }
if (-not (Test-Path $script))  { throw "share_server.py not found at $script" }

# --- 1. skill junctions ------------------------------------------------------
foreach ($skillLink in $skillLinks) {
    $existing = Get-Item $skillLink -EA SilentlyContinue
    if ($existing) {
        if ($existing.LinkType -eq "Junction") {
            [System.IO.Directory]::Delete($skillLink)
        } else {
            throw "$skillLink exists and is a real directory, not a junction. Move it aside first."
        }
    }
    New-Item -ItemType Directory -Force (Split-Path -Parent $skillLink) | Out-Null
    cmd /c mklink /J "`"$skillLink`"" "`"$skillSrc`"" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "failed to create junction at $skillLink" }
    "Linked skill: $skillLink -> $skillSrc"
}

# --- 2. scheduled task -------------------------------------------------------
$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "`"$script`" --port $Port --log `"$log`"" `
    -WorkingDirectory $root

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME

# Interactive so it shares the desktop session's network context; no elevation
# needed because we bind a high port.
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

"Registered scheduled task '$TaskName' (starts at logon, port $Port)."
"  log: $log"
"  uninstall: powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Uninstall"
