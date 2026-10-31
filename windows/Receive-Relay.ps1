#Requires -Version 7.0
<# Trusted GENESIS Relay receiver. This file belongs to the Relay distribution,
   never to an imported capsule. Inspect/Plan do not execute capsule scripts. #>
[CmdletBinding()]
param(
 [Parameter(Mandatory)][ValidateSet('Inspect','Plan','Restore','Verify','Open','LaunchCodex','Return','ReturnInspect','ReturnPreview','ReturnApply','ReturnRollback')][string]$Operation,
 [string]$Capsule,[string]$Root,[string]$Receipt,[string]$Project,[string]$Output,[string]$ReturnCapsule,[string]$Plan,
 [ValidateSet('NATIVE_WINDOWS_X64','WSL_LINUX_X64','LOCAL_LINUX')][string]$Route='NATIVE_WINDOWS_X64',
 [string]$Python,[string]$WslDistribution,[string]$WslPython='python3',[string[]]$Selected,[switch]$Apply
)
$ErrorActionPreference='Stop'
$bundledExe=Join-Path $PSScriptRoot 'Genesis-Relay.exe'
if(-not(Test-Path -LiteralPath $bundledExe)){$bundledExe=Join-Path $PSScriptRoot '../Genesis-Relay.exe'}
$hasBundledExe=$IsWindows -and (Test-Path -LiteralPath $bundledExe)
$trustedSource=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../src'))
$hasTrustedSource=Test-Path (Join-Path $trustedSource 'genesis_relay/receive_cli.py')
$bootstrap='import sys; sys.path.insert(0,sys.argv.pop(1)); from genesis_relay.receive_cli import main; raise SystemExit(main())'
if($Operation -in @('Plan','Restore')){
 if(-not $Root){
  if($IsWindows -and (Test-Path 'E:\')){$Root='E:\GENESIS-RELAY'}
  else{throw 'E: is unavailable. Supply an explicit -Root. No alternate project root is selected silently.'}
 }
}
$dispatch=[System.Collections.Generic.List[string]]::new();$dispatch.Add($Operation)
function Add-Argument([string]$Name,[string]$Value){if($Value){$dispatch.Add($Name);$dispatch.Add($Value)}}
function Convert-WslPath([string]$Value){
 if(-not $Value){return $Value}
 if($Value.StartsWith('/')){return $Value}
 $valueOut=& $script:wslExe -d $WslDistribution -- wslpath -a -u $Value
 if($LASTEXITCODE -ne 0){throw 'WSL path conversion failed. Nothing restored.'}
 return ($valueOut | Select-Object -Last 1).Trim()
}
if($Route -eq 'WSL_LINUX_X64' -and $Operation -ne 'Inspect'){
 if(-not $IsWindows){throw 'PowerShell WSL dispatch must run on Windows with actual WSL. Linux PowerShell is not Windows/WSL acceptance.'}
 if(-not $WslDistribution){throw 'Choose an existing WSL distribution explicitly with -WslDistribution.'}
 $script:wslExe=(Get-Command wsl.exe -CommandType Application -ErrorAction Stop).Source
 $trustedWsl=if($hasTrustedSource){Convert-WslPath $trustedSource}else{$null}
 $Capsule=Convert-WslPath $Capsule;$Root=Convert-WslPath $Root;$Receipt=Convert-WslPath $Receipt;$Project=Convert-WslPath $Project;$Output=Convert-WslPath $Output;$ReturnCapsule=Convert-WslPath $ReturnCapsule;$Plan=Convert-WslPath $Plan
 Add-Argument '--capsule' $Capsule;Add-Argument '--destination-root' $Root;Add-Argument '--receipt' $Receipt;Add-Argument '--project' $Project;Add-Argument '--output' $Output;Add-Argument '--return-capsule' $ReturnCapsule;Add-Argument '--plan' $Plan;Add-Argument '--route' $Route
 foreach($name in $Selected){Add-Argument '--selected' $name};if($Apply){$dispatch.Add('--apply')}
 if($trustedWsl){& $script:wslExe -d $WslDistribution -- $WslPython -I -c $bootstrap $trustedWsl @dispatch}
 else{& $script:wslExe -d $WslDistribution -- $WslPython -I -m genesis_relay.receive_cli @dispatch}
 if($LASTEXITCODE -ne 0){throw "WSL receiver failed with exit $LASTEXITCODE. Review its receipt and blocked prerequisites."}
 exit 0
}
if(-not $Python -and -not $hasBundledExe){$Python=(Get-Command python -CommandType Application -ErrorAction Stop).Source}
function Invoke-TrustedRelay([string[]]$RelayArguments){
 if($hasBundledExe){& $bundledExe 'receive' @RelayArguments}
 elseif($hasTrustedSource){& $Python -I -c $bootstrap $trustedSource @RelayArguments}
 else{& $Python -I -m genesis_relay.receive_cli @RelayArguments}
}
try{
 if($Operation -eq 'LaunchCodex'){
  if(-not $Apply){throw 'LaunchCodex requires -Apply after project review.'}
  if(-not $Receipt){throw 'LaunchCodex requires an existing receiver receipt.'}
  $infoRaw=Invoke-TrustedRelay -RelayArguments @('Info','--receipt',$Receipt)
  if($LASTEXITCODE -ne 0){throw 'Cannot validate receiver workspace.'}
  $info=($infoRaw -join "`n") | ConvertFrom-Json
  $codex=Get-Command codex -ErrorAction Stop
  # Argument array and PowerShell invocation operator preserve spaces/metacharacters.
  # No authentication/config/version flags are changed and no CLI is installed.
  Push-Location -LiteralPath $info.project_path
  try{& $codex.Source '-C' ([string]$info.project_path)}finally{Pop-Location}
  exit $LASTEXITCODE
 }
 Add-Argument '--capsule' $Capsule;Add-Argument '--destination-root' $Root;Add-Argument '--receipt' $Receipt;Add-Argument '--project' $Project;Add-Argument '--output' $Output;Add-Argument '--return-capsule' $ReturnCapsule;Add-Argument '--plan' $Plan;Add-Argument '--route' $Route
 foreach($name in $Selected){Add-Argument '--selected' $name};if($Apply){$dispatch.Add('--apply')}
 Invoke-TrustedRelay -RelayArguments ($dispatch.ToArray())
 if($LASTEXITCODE -ne 0){throw "Relay receiver failed with exit $LASTEXITCODE. Existing unrelated projects were not selected for overwrite."}
}finally{ # No user-wide environment, Codex or shell configuration was changed.
}
