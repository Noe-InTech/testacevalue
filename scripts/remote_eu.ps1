# Exécute une commande sur le runner EU via SSH (OVH ou autre).
# Prérequis : runner/ovh.local.env + ~/.ssh/config (Host aces-eu)
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$RemoteCommand
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path "$Root\runner\ovh.local.env")) {
  Write-Error "Crée runner/ovh.local.env depuis runner/ovh.local.env.example"
}
Get-Content "$Root\runner\ovh.local.env" | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    Set-Item -Path "env:$($Matches[1])" -Value $Matches[2].Trim()
  }
}
$hostName = $env:RUNNER_SSH_HOST
$user = if ($env:RUNNER_SSH_USER) { $env:RUNNER_SSH_USER } else { "debian" }
$key = if ($env:RUNNER_SSH_KEY) { $env:RUNNER_SSH_KEY } else { "$env:USERPROFILE\.ssh\oracle_aces" }
$sshArgs = @("-o", "ConnectTimeout=20", "-o", "StrictHostKeyChecking=accept-new")
if ($hostName -match '^[A-Za-z][A-Za-z0-9-]*$' -and $hostName -notmatch '^\d') {
  & ssh @sshArgs $hostName $RemoteCommand
} else {
  $target = if ($hostName -match '@') { $hostName } else { "${user}@${hostName}" }
  & ssh @sshArgs -i $key $target $RemoteCommand
}
