[CmdletBinding()]
param([switch]$Build)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
if($Build){Push-Location $root;try{npm run build;if($LASTEXITCODE -ne 0){throw 'Build failed'}}finally{Pop-Location}}
$ssh=@('-F','NUL','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10')
& ssh @ssh 'venom@100.83.89.28' 'mkdir -p /home/venom/website-router-deploy && chmod 700 /home/venom/website-router-deploy'
if($LASTEXITCODE -ne 0){throw 'SSH staging failed'}
& scp @ssh (Join-Path $root 'dist/server.mjs') (Join-Path $root 'dist/probe.mjs') (Join-Path $PSScriptRoot 'deploy-ubuntu.py') (Join-Path $PSScriptRoot 'activate-ubuntu.py') 'venom@100.83.89.28:/home/venom/website-router-deploy/'
if($LASTEXITCODE -ne 0){throw 'Code upload failed'}
& (Join-Path $PSScriptRoot 'invoke-ubuntu.ps1') -RemoteCommand 'python3 /home/venom/website-router-deploy/deploy-ubuntu.py' -IncludeProvider
Write-Output 'Encrypted registry synchronized. Existing tunnel identity is preserved. Restart the local Codex plugin after configuration changes.'
