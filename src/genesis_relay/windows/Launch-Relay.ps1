#Requires -Version 7.0
<# Starts the trusted local UI. Relay itself needs no external Python when the
   adjacent Windows executable distribution is used. Project dependencies differ. #>
[CmdletBinding()]
param([ValidateSet('start','access','status','stop','restart')][string]$Operation='start',[string]$StateDir,[string]$Source,[int]$Port=0)
$ErrorActionPreference='Stop'
$exe=Join-Path $PSScriptRoot 'Genesis-Relay.exe'
if(-not(Test-Path -LiteralPath $exe)){$exe=Join-Path $PSScriptRoot '../Genesis-Relay.exe'}
if(-not(Test-Path -LiteralPath $exe)){throw 'Use this launcher from the intact trusted Windows executable ZIP.'}
$call=[System.Collections.Generic.List[string]]::new()
if($StateDir){$call.Add('--state-dir');$call.Add($StateDir)}
$call.Add('ui');$call.Add($Operation)
if($Source){$call.Add('--source');$call.Add($Source)}
if($Port){$call.Add('--port');$call.Add([string]$Port)}
& $exe @call
exit $LASTEXITCODE
