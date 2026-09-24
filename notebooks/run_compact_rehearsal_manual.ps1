param([switch]$CheckOnly)
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
Set-Location $project
$manifest='outputs/phase1/p1-025/manual-source-hashes.json'
$expected=Get-Content -Raw $manifest | ConvertFrom-Json
foreach($entry in $expected.PSObject.Properties) {
    if((Get-FileHash $entry.Name -Algorithm SHA256).Hash.ToLower() -ne $entry.Value) {
        throw ('Reviewed file changed: '+$entry.Name)
    }
}
$probe=Get-Content -Raw outputs/phase1/p1-023/atomic-probe/report.json | ConvertFrom-Json
if($probe.status -ne 'passed') { throw 'Windows publication probe has not passed' }
$output='outputs/phase1/p1-025/manual-compact-01'
if(Test-Path $output) { throw 'This attempt already exists. Preserve it and review its report before any new run.' }
if($CheckOnly) { Write-Output 'READY: source hashes and Windows publication probe verified; no model loaded.'; exit 0 }
$lock=[System.IO.File]::Open((Join-Path $project 'outputs/phase1/p1-023/manual.lock'),[System.IO.FileMode]::OpenOrCreate,[System.IO.FileAccess]::ReadWrite,[System.IO.FileShare]::None)
try {
    $env:HF_HUB_OFFLINE='1'
    $env:TRANSFORMERS_OFFLINE='1'
    $env:HF_DEACTIVATE_ASYNC_LOAD='1'
    $env:CUBLAS_WORKSPACE_CONFIG=':4096:8'
    Write-Output 'Running the bounded rehearsal. Leave this terminal connected. No Codex session is needed.'
    & '.\.venv\Scripts\python.exe' -B notebooks/check_remote_rehearsal.py --compact --output-dir $output
    $code=$LASTEXITCODE
    $report=Join-Path $output 'report.json'
    if(Test-Path $report) {
        $r=Get-Content -Raw $report | ConvertFrom-Json
        [pscustomobject]@{
            status=$r.status
            error=$r.error
            forward_counts=@($r.attempts | ForEach-Object {$_.state.forward_calls})
            compact_storage=$r.compact_storage
            multi_hour_ready=$false
            report=$report
        } | ConvertTo-Json -Depth 4
    }
    Write-Output 'Finished. Copy the summary above for review; do not rerun on a failure.'
    exit $code
} finally { $lock.Dispose() }
