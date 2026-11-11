# Read-only diagnostics. No Set/Initialize/New/Format, ACL setters or elevation.
# Raw volume/disk identifiers exist only in memory and are never emitted.
$ErrorActionPreference = 'Stop'
$result = [ordered]@{
    probe = 'storage_readonly'
    operational_approval = 'NONE'
    drives = @()
    volume_ids_different = $null
    disks_different = $null
    disk_ids_different = $null
}
$observed = @{}
foreach ($driveLetter in @('C', 'E')) {
    try {
        $volume = Get-Volume -DriveLetter $driveLetter -ErrorAction Stop
        $parts = @(Get-Partition -DriveLetter $driveLetter -ErrorAction Stop)
        if ($parts.Count -ne 1) {
            throw [InvalidOperationException]::new('ambiguous mapping')
        }
        $disk = Get-Disk -Number $parts[0].DiskNumber -ErrorAction Stop
        $observed[$driveLetter] = @{
            VolumeId = [string]$volume.UniqueId
            DiskId = [string]$disk.UniqueId
            DiskNumber = [int]$disk.Number
        }
        $result.drives += [ordered]@{
            drive = $driveLetter
            query = 'SUCCESS'
            filesystem = [string]$volume.FileSystemType
            drive_type = [string]$volume.DriveType
            disk_number = [int]$disk.Number
            partition_mapping_count = $parts.Count
            volume_identifier_present = -not [string]::IsNullOrWhiteSpace([string]$volume.UniqueId)
            disk_identifier_present = -not [string]::IsNullOrWhiteSpace([string]$disk.UniqueId)
            disk_is_offline = [bool]$disk.IsOffline
            disk_is_readonly = [bool]$disk.IsReadOnly
            bus_type = [string]$disk.BusType
        }
    } catch {
        $result.drives += [ordered]@{
            drive = $driveLetter
            query = 'UNVERIFIED'
            error_type = $_.Exception.GetType().Name
        }
    }
}
if ($observed.ContainsKey('C') -and $observed.ContainsKey('E')) {
    $result.disks_different = $observed['C'].DiskNumber -ne $observed['E'].DiskNumber
    if ($observed['C'].VolumeId -and $observed['E'].VolumeId) {
        $result.volume_ids_different = $observed['C'].VolumeId -ne $observed['E'].VolumeId
    }
    if ($observed['C'].DiskId -and $observed['E'].DiskId) {
        $result.disk_ids_different = $observed['C'].DiskId -ne $observed['E'].DiskId
    }
}
$result | ConvertTo-Json -Depth 5 -Compress
