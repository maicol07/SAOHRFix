<#
.SYNOPSIS
  Reversibly disable/enable third-party mods in the SAO HR game folder for VANILLA runtime tests.

.DESCRIPTION
  'off' renames known injector/mod files to "<name>.saohrfix-off"; 'on' restores them.
  'status' lists what is present. Never deletes files, never touches sao_hr.exe or pkg/.
  Special K global injection is NOT file-based in the game folder: stop it from SKIF
  (Special K Injection Frontend) before a vanilla test.

.EXAMPLE
  .\tools\mods.ps1 status
  .\tools\mods.ps1 off
  .\tools\mods.ps1 on
#>
param(
    [Parameter(Mandatory)][ValidateSet('status', 'off', 'on')][string]$Action
)
$ErrorActionPreference = 'Stop'
$GameDir = 'W:\SteamLibrary\steamapps\common\SAOHR'
$Suffix = '.saohrfix-off'
# Proxy DLL names used by Ultimate ASI Loader / ReShade / Special K local installs, plus plugins.
$ProxyNames = @('d3d11.dll', 'dxgi.dll', 'dinput8.dll', 'winmm.dll', 'version.dll', 'd3d9.dll', 'opengl32.dll')
$PluginPatterns = @('*.asi', '*.addon64', '*.addon')

function Get-ModFiles([bool]$Disabled) {
    $tail = if ($Disabled) { $Suffix } else { '' }
    $names = $ProxyNames | ForEach-Object { "$_$tail" }
    $byName = $names | ForEach-Object { Join-Path $GameDir $_ } | Where-Object { Test-Path -LiteralPath $_ }
    $byPattern = $PluginPatterns | ForEach-Object { Get-ChildItem -LiteralPath $GameDir -Filter "$_$tail" -File } |
        ForEach-Object FullName
    @($byName) + @($byPattern) | Sort-Object -Unique
}

switch ($Action) {
    'status' {
        "active:";   Get-ModFiles $false | ForEach-Object { "  $_" }
        "disabled:"; Get-ModFiles $true  | ForEach-Object { "  $_" }
    }
    'off' { Get-ModFiles $false | ForEach-Object { Rename-Item -LiteralPath $_ -NewName ((Split-Path $_ -Leaf) + $Suffix); "off: $_" } }
    'on'  { Get-ModFiles $true  | ForEach-Object { Rename-Item -LiteralPath $_ -NewName ((Split-Path $_ -Leaf) -replace ([regex]::Escape($Suffix) + '$'), ''); "on:  $_" } }
}
