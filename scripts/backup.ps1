param(
    [string]$BackupDir = "backups"
)

$ErrorActionPreference = "Stop"

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*#" -or $_ -notmatch "=") { return }
        $name, $value = $_ -split "=", 2
        [Environment]::SetEnvironmentVariable($name.Trim(), $value.Trim(), "Process")
    }
}

New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$backupAbs = (Resolve-Path $BackupDir).Path
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"

$dbBackup = Join-Path $BackupDir "ctfd_db_$stamp.sql"
$piholeBackup = Join-Path $BackupDir "pihole_config_$stamp.tar.gz"

Write-Host "Backing up CTFd database to $dbBackup"
docker exec ctfd-db mariadb-dump -u ctfd "-p$env:CTFD_DB_PASSWORD" ctfd | Set-Content -Encoding UTF8 $dbBackup

Write-Host "Backing up Pi-hole config to $piholeBackup"
docker run --rm --volumes-from pihole -v "${backupAbs}:/backup" alpine:3.22 `
    tar czf "/backup/pihole_config_$stamp.tar.gz" -C /etc pihole dnsmasq.d

Write-Host "Backup complete"
