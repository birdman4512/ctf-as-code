param(
    [Parameter(Mandatory = $true)]
    [string]$DatabaseBackup,

    [string]$PiholeBackup
)

$ErrorActionPreference = "Stop"

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*#" -or $_ -notmatch "=") { return }
        $name, $value = $_ -split "=", 2
        [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
    }
}

if (-not (Test-Path $DatabaseBackup)) {
    throw "Database backup not found: $DatabaseBackup"
}

Write-Host "Restoring CTFd database from $DatabaseBackup"
Get-Content -Raw $DatabaseBackup | docker exec -i ctfd-db mariadb -u root "-p$env:CTFD_DB_ROOT_PASSWORD" ctfd

if ($PiholeBackup) {
    if (-not (Test-Path $PiholeBackup)) {
        throw "Pi-hole backup not found: $PiholeBackup"
    }

    Write-Host "Restoring Pi-hole config from $PiholeBackup"
    $backupPath = Resolve-Path $PiholeBackup
    $backupName = Split-Path $backupPath -Leaf
    $backupDir = Split-Path $backupPath -Parent

    docker run --rm --volumes-from pihole -v "${backupDir}:/backup" alpine:3.22 `
        sh -c "rm -rf /etc/pihole/* /etc/dnsmasq.d/* && tar xzf /backup/$backupName -C /etc"
}

Write-Host "Restore complete. Restart services with: docker compose restart"
