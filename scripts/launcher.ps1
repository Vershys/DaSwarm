# DaSwarm single-program Windows launcher. Requires Docker Desktop, no Python or Node install.
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression.FileSystem
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:LOCALAPPDATA 'DaSwarm'
$project = Join-Path $root 'project'
$log = Join-Path $root 'launcher.log'
New-Item -ItemType Directory -Force -Path $root | Out-Null
if ($env:DASWARM_BUNDLE) {
    $bundle = $env:DASWARM_BUNDLE
} else {
    $bundle = Join-Path $PSScriptRoot 'project.zip'
}
if (!(Test-Path (Join-Path $project 'docker-compose.yml'))) {
    if (!(Test-Path $bundle)) { throw 'The embedded project bundle is missing.' }
    [IO.Compression.ZipFile]::ExtractToDirectory($bundle, $project)
}
$envFile = Join-Path $project '.env'
if (!(Test-Path $envFile)) {
    $dbSecret = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
    $storeSecret = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
    @"
API_KEY=simulation-placeholder
API_BASE=http://mockserver:8090/v1
AUTH_PROVIDER=none
SWARM_ENABLED=true
SWARM_DB_PASSWORD=$dbSecret
SWARM_OBJECT_STORE_ACCESS_KEY=manus-local
SWARM_OBJECT_STORE_SECRET_KEY=$storeSecret
CELERY_CONCURRENCY=4
SWARM_BROWSER_CONCURRENCY=4
SWARM_GPU_CONCURRENCY=1
SWARM_RENDER_CONCURRENCY=1
"@ | Set-Content -Encoding UTF8 $envFile
}
$form = New-Object Windows.Forms.Form
$form.Text = 'DaSwarm / Runtime Control'
$form.Size = New-Object Drawing.Size(850,640)
$form.StartPosition = 'CenterScreen'
$form.BackColor = [Drawing.Color]::FromArgb(16,24,34)
$form.ForeColor = [Drawing.Color]::FromArgb(221,232,243)
$form.Font = New-Object Drawing.Font('Segoe UI',10)
$title = New-Object Windows.Forms.Label
$title.Text = 'DASWARM  /  LOCAL CONTROL PLANE'
$title.Location = New-Object Drawing.Point(24,24)
$title.Size = New-Object Drawing.Size(760,30)
$title.Font = New-Object Drawing.Font('Segoe UI',16,[Drawing.FontStyle]::Bold)
$form.Controls.Add($title)
$desc = New-Object Windows.Forms.Label
$desc.Text = 'Start the backend, worker fleet, storage and command center from one program.'
$desc.Location = New-Object Drawing.Point(24,64)
$desc.Size = New-Object Drawing.Size(780,35)
$form.Controls.Add($desc)
$status = New-Object Windows.Forms.Label
$status.Text = 'Ready. Docker Desktop must be running. First build can take several minutes.'
$status.Location = New-Object Drawing.Point(24,153)
$status.Size = New-Object Drawing.Size(780,40)
$form.Controls.Add($status)
$output = New-Object Windows.Forms.TextBox
$output.Multiline = $true
$output.ReadOnly = $true
$output.ScrollBars = 'Both'
$output.WordWrap = $false
$output.Location = New-Object Drawing.Point(24,205)
$output.Size = New-Object Drawing.Size(785,330)
$output.BackColor = [Drawing.Color]::FromArgb(10,16,24)
$output.ForeColor = [Drawing.Color]::FromArgb(161,192,214)
$output.Font = New-Object Drawing.Font('Consolas',9)
$output.Anchor = 'Top,Bottom,Left,Right'
$form.Controls.Add($output)
$footer = New-Object Windows.Forms.Label
$footer.Text = 'Simulation by default. Closing this window leaves services running. Stop preserves data.'
$footer.Location = New-Object Drawing.Point(24,550)
$footer.Size = New-Object Drawing.Size(785,35)
$footer.Anchor = 'Bottom,Left,Right'
$form.Controls.Add($footer)
$script:process = $null
$script:opening = $false
function Launch-Compose([string]$arguments) {
    if ($script:process -and !$script:process.HasExited) { return }
    if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
        [Windows.Forms.MessageBox]::Show('Install Docker Desktop from docker.com, start it, then reopen DaSwarm.','Docker Desktop required') | Out-Null
        return
    }
    $script:process = Start-Process -FilePath 'docker' -ArgumentList ('compose -p daswarm '+$arguments) -WorkingDirectory $project -RedirectStandardOutput $log -RedirectStandardError (Join-Path $root 'launcher-errors.log') -PassThru -WindowStyle Hidden
    $status.Text = 'Running: docker compose '+$arguments
}
function Button([string]$text,[int]$x,[scriptblock]$action) {
    $b=New-Object Windows.Forms.Button
    $b.Text=$text;$b.Location=New-Object Drawing.Point($x,105);$b.Size=New-Object Drawing.Size(145,34)
    $b.BackColor=[Drawing.Color]::FromArgb(32,51,67);$b.ForeColor=$form.ForeColor;$b.FlatStyle='Flat'
    $b.Add_Click($action);$form.Controls.Add($b)
}
Button 'Start / Build' 24 { $script:opening=$true; Launch-Compose 'up -d --build' }
Button 'Open Console' 181 { Start-Process 'http://localhost:5173/swarm' }
Button 'Stop Services' 338 { Launch-Compose 'stop' }
Button 'Configuration' 495 { Start-Process notepad.exe $envFile }
Button 'Project / Plugins' 652 { Start-Process explorer.exe $project }
$timer = New-Object Windows.Forms.Timer
$timer.Interval=1500
$timer.Add_Tick({
    try {
        $text = ''
        if(Test-Path $log) {$text += (Get-Content $log -Tail 120) -join "`r`n"}
        $errors = Join-Path $root 'launcher-errors.log'
        if(Test-Path $errors) {$text += "`r`n" + ((Get-Content $errors -Tail 60) -join "`r`n")}
        if($output.Text -ne $text){$output.Text=$text;$output.SelectionStart=$output.Text.Length;$output.ScrollToCaret()}
        if($script:process -and $script:process.HasExited){
            $exit=$script:process.ExitCode;$script:process=$null
            if($exit -eq 0){$status.Text='Services updated successfully.';if($script:opening){Start-Process 'http://localhost:5173/swarm'}}
            else {$status.Text='Docker reported an error. See the log below. Existing data is preserved.'}
            $script:opening=$false
        }
    } catch {$status.Text='Waiting for runtime output…'}
})
$timer.Start()
[void]$form.ShowDialog()
$timer.Stop()
