# Actualizador de Controlador ChatGPT (no instala ni modifica la app oficial de ChatGPT).
# Nunca descarga ni ejecuta codigo de la red; solo instala contenido de un ZIP elegido.
Add-Type -AssemblyName System.Windows.Forms
$ErrorActionPreference = 'Stop'
[System.Windows.Forms.Application]::EnableVisualStyles()
function Say([string]$message, [string]$heading='Controlador ChatGPT') {
    [System.Windows.Forms.MessageBox]::Show($message, $heading, 'OK', 'Information') | Out-Null
}
try {
    $pickZip = New-Object System.Windows.Forms.OpenFileDialog
    $pickZip.Title = 'Elige el ZIP de la nueva version del controlador'
    $pickZip.Filter = 'Archivos ZIP (*.zip)|*.zip'
    if ($pickZip.ShowDialog() -ne 'OK') { return }
    $pickDir = New-Object System.Windows.Forms.FolderBrowserDialog
    $pickDir.Description = 'Selecciona la carpeta donde esta instalado el controlador anterior (no ChatGPT)'
    $pickDir.SelectedPath = Split-Path -Parent $PSCommandPath
    if ($pickDir.ShowDialog() -ne 'OK') { return }
    $target = [IO.Path]::GetFullPath($pickDir.SelectedPath)
    if (-not (Test-Path (Join-Path $target 'controller.py')) -and -not (Test-Path (Join-Path $target 'ControladorChatGPT.exe'))) {
        throw 'La carpeta no contiene un controlador anterior reconocible. No se ha cambiado nada.'
    }
    $resp = [System.Windows.Forms.MessageBox]::Show(
        "Cierra el controlador antes de actualizarlo.`n`nOrigen: $($pickZip.FileName)`nDestino: $target`n`nSe preservara la configuracion guardada en LOCALAPPDATA. Continuar?",
        'Confirmar actualizacion', 'YesNo', 'Warning')
    if ($resp -ne 'Yes') { return }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [IO.Compression.ZipFile]::OpenRead($pickZip.FileName)
    $staging = Join-Path $env:TEMP ('ChatGPT_Update_' + [guid]::NewGuid().ToString('N'))
    [IO.Directory]::CreateDirectory($staging) | Out-Null
    $backup = Join-Path $env:LOCALAPPDATA ('ControladorChatGPT\backups\' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    [IO.Directory]::CreateDirectory($backup) | Out-Null
    $allowedExtensions = @('.py', '.bat', '.ps1', '.md', '.txt', '.exe', '.yml', '.yaml', '.json', '.c')
    $files = @()
    $totalSize = [int64]0
    try {
        foreach ($entry in $archive.Entries) {
            $path = $entry.FullName.Replace('\','/')
            if (-not $path.StartsWith('ControladorChatGPT/', [StringComparison]::Ordinal)) { throw "ZIP inesperado: $path" }
            if ($path.EndsWith('/')) { continue }
            $relative = $path.Substring('ControladorChatGPT/'.Length)
            if (-not $relative -or $relative.StartsWith('/') -or $relative.Contains(':') -or
                ($relative.Split('/') | Where-Object { $_ -eq '..' -or $_ -eq '.' }).Count -gt 0) {
                throw "Ruta no permitida en ZIP: $relative"
            }
            $extension = [IO.Path]::GetExtension($relative).ToLowerInvariant()
            if ($allowedExtensions -notcontains $extension) { throw "Extension inesperada: $relative" }
            $totalSize += $entry.Length
            if ($entry.Length -gt 150MB -or $totalSize -gt 350MB -or $files.Count -gt 300) { throw 'El ZIP supera los limites de seguridad.' }
            # Reject symbolic links or other Unix special types (high 16 bits: file type mask).
            $unixMode = ($entry.ExternalAttributes -shr 16) -band 0xF000
            if ($unixMode -ne 0 -and $unixMode -ne 0x8000) { throw "Entrada especial no permitida: $relative" }
            $out = [IO.Path]::GetFullPath((Join-Path $staging ($relative.Replace('/','\'))))
            if (-not $out.StartsWith(($staging + [IO.Path]::DirectorySeparatorChar), [StringComparison]::OrdinalIgnoreCase)) {
                throw "Ruta fuera del directorio temporal: $relative"
            }
            [IO.Directory]::CreateDirectory((Split-Path $out)) | Out-Null
            [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $out, $true)
            $files += $relative
        }
        if ($files -notcontains 'controller.py' -or $files -notcontains 'app_adapter.py' -or $files -notcontains 'chat_discovery.py') {
            throw 'El ZIP no contiene los modulos obligatorios de la version 4.'
        }
        $done = New-Object System.Collections.ArrayList
        foreach ($relative in $files) {
            $normalized = $relative.Replace('/','\')
            $src = Join-Path $staging $normalized
            $dst = Join-Path $target $normalized
            [IO.Directory]::CreateDirectory((Split-Path $dst)) | Out-Null
            if (Test-Path -LiteralPath $dst) {
                $saved = Join-Path $backup $normalized
                [IO.Directory]::CreateDirectory((Split-Path $saved)) | Out-Null
                Copy-Item -LiteralPath $dst -Destination $saved -Force
            }
            try {
                Copy-Item -LiteralPath $src -Destination $dst -Force
                [void]$done.Add($relative)
            } catch {
                foreach ($previous in $done) {
                    $old = Join-Path $backup ($previous.Replace('/','\'))
                    $installed = Join-Path $target ($previous.Replace('/','\'))
                    if (Test-Path -LiteralPath $old) { Copy-Item -LiteralPath $old -Destination $installed -Force }
                    elseif (Test-Path -LiteralPath $installed) { Remove-Item -LiteralPath $installed -Force }
                }
                throw
            }
        }
        Say "Actualizacion instalada.`n`nArchivos: $($files.Count)`nCopia de seguridad: $backup`n`nVuelve a abrir el controlador."
    } finally {
        $archive.Dispose()
        if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    }
} catch {
    [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Actualizacion detenida sin confirmacion de exito', 'OK', 'Error') | Out-Null
}
