param([ValidateSet('Start','Status','Stop','CheckOnly','Probe')][string]$Action='Status')
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$root=Split-Path (Split-Path $project -Parent) -Parent
$base=Join-Path $project 'outputs\phase1\p1-027'
$output=Join-Path $base 'manual-sustained-01'
Set-Location $project
if($Action -eq 'Status') {
    $report=Join-Path $output 'report.json'
    if(Test-Path $report) {
        $r=Get-Content -Raw $report | ConvertFrom-Json
        $latest=$r.attempts | Select-Object -Last 1
        $state=$null
        if($latest) {
            $path=Join-Path $output ($latest.label+'\attempt.json')
            if(Test-Path $path) {$state=Get-Content -Raw $path | ConvertFrom-Json}
        }
        [pscustomobject]@{status=$r.status;error=$r.error;attempt=$latest.label;worker_status=$state.status;completed=$state.executed;skipped=$state.skipped;forward_calls=$state.forward_calls;comparison=$r.comparison;report=$report} | ConvertTo-Json -Depth 5
    } else {Write-Output 'Not started.'}
    exit 0
}
if($Action -eq 'Stop') {
    if(-not (Test-Path $output)) {throw 'No run exists.'}
    New-Item -ItemType File -Path (Join-Path $output 'STOP') -Force | Out-Null
    Write-Output 'Stop requested. Check Status shortly; retain the outputs.'
    exit 0
}
$expected=Get-Content -Raw (Join-Path $base 'manual-source-hashes.json') | ConvertFrom-Json
foreach($entry in $expected.PSObject.Properties) {
    if((Get-FileHash $entry.Name -Algorithm SHA256).Hash.ToLower() -ne $entry.Value) {throw ('Reviewed file changed: '+$entry.Name)}
}
$task=Get-ScheduledTask -TaskPath '\Research\' -TaskName 'PythonJob'
if($task.State -ne 'Ready') {throw 'The existing PythonJob slot is not idle; do not overwrite its manifest.'}
if($Action -ne 'Probe') {
    $probe=Get-Content -Raw (Join-Path $base 'launcher-probe\report.json') | ConvertFrom-Json
    if($probe.status -ne 'passed') {throw 'Scheduled-launch probe has not passed.'}
    if(Test-Path $output) {throw 'This attempt exists. Preserve it; do not rerun.'}
}
if($Action -eq 'CheckOnly') {Write-Output 'READY: fixed overnight plan and scheduled-launch probe verified; no model loaded.';exit 0}
$manifest=Join-Path $root 'runs\current-job.json'
$backup=Join-Path $base 'previous-current-job.json'
if(-not (Test-Path $backup)) {Copy-Item -LiteralPath $manifest -Destination $backup}
$jobArgs=@()
if($Action -eq 'Probe') {$jobArgs=@('--probe')}
$entry=[ordered]@{script=(Join-Path $project 'notebooks\launch_remote_sustained.py');args=@($jobArgs);cwd=$project;log=(Join-Path $base ('scheduled-'+$Action.ToLower()+'.log'))}
$entry | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifest -Encoding UTF8
Start-ScheduledTask -TaskPath '\Research\' -TaskName 'PythonJob'
Write-Output 'Start requested in the existing scheduled PythonJob slot. Use Status to confirm progress. Keep Windows awake and powered; SSH may disconnect.'
