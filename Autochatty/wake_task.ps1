param(
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [string]$ScriptPath = "",
    [Parameter(Mandatory=$true)][string]$Times
)
$ErrorActionPreference = 'Stop'
$triggers = @()
foreach ($item in ($Times -split ',')) {
    $value = $item.Trim()
    $dt = [datetime]::ParseExact($value, 'HH:mm', [Globalization.CultureInfo]::InvariantCulture)
    $triggers += New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.Add($dt.TimeOfDay))
}
if ($triggers.Count -eq 0) { throw 'Se necesita al menos una hora.' }
$arguments = if ([string]::IsNullOrWhiteSpace($ScriptPath)) { '' } else { '"' + $ScriptPath + '"' }
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument $arguments
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 0)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'ControladorChatGPT_Despertar' -Trigger $triggers -Action $action -Settings $settings -Principal $principal -Description 'Activa el controlador para continuar chats pendientes' -Force | Out-Null
Write-Output 'Despertador configurado'
