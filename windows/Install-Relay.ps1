#Requires -Version 7.0
<# Explicit optional bootstrap. Uses an existing Python; never installs a second
   distribution, edits Codex, activates source capsule hooks or runs capsule code. #>
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Wheel,[string]$Root,[string]$Python,[switch]$Apply)
$ErrorActionPreference='Stop'
if(-not $Apply){throw 'Inspect INSTALL instructions first, then invoke this trusted bootstrap explicitly with -Apply.'}
if(-not $Root){if($IsWindows -and(Test-Path 'E:\')){$Root='E:\GENESIS-RELAY'}else{throw 'E: is unavailable; supply an explicit -Root.'}}
if(-not $Python){$Python=(Get-Command python -CommandType Application -ErrorAction Stop).Source}
if(-not(Test-Path -LiteralPath $Wheel -PathType Leaf)){throw 'Select an existing verified Relay wheel.'}
$venv=Join-Path $Root 'receiver-venv'
if(Test-Path -LiteralPath $venv){throw 'Refusing to overwrite an existing receiver environment. Select another explicit root.'}
New-Item -ItemType Directory -Path $Root -Force | Out-Null
& $Python -I -m venv $venv
if($LASTEXITCODE -ne 0){throw 'The existing Python could not create a project-local venv.'}
$targetPython=if($IsWindows){Join-Path $venv 'Scripts/python.exe'}else{Join-Path $venv 'bin/python'}
& $targetPython -I -m pip install --no-index --no-deps $Wheel
if($LASTEXITCODE -ne 0){throw 'Relay installation failed; partial environment retained for review.'}
Write-Output "Installed trusted Relay receiver in $venv. No foreign scientific environment was copied or claimed reconstructed."
Write-Output "Use Receive-Relay.ps1 -Python '$targetPython' -Operation Inspect -Capsule '<verified capsule path>'."
