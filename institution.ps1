param(
    [ValidateSet('login', 'status', 'download', 'list', 'test')]
    [string]$Action = 'status',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ExtraArgs
)

# 只在当前脚本进程中切换配置，不修改用户级环境变量和全局 Skill。
$institutionRoot = $PSScriptRoot
$institutionPython = Join-Path $institutionRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $institutionPython)) {
    $institutionPython = 'python'
}
$savedRoot = $env:GLEANERA_ROOT
$savedPython = $env:GLEANERA_PYTHON
$savedChannel = $env:ACQ_BROWSER_CHANNEL
try {
    $env:GLEANERA_ROOT = $institutionRoot
    $env:GLEANERA_PYTHON = $institutionPython
    if (-not $env:ACQ_BROWSER_CHANNEL) { $env:ACQ_BROWSER_CHANNEL = 'msedge' }
    switch ($Action) {
        'login' { & $institutionPython (Join-Path $institutionRoot 'login.py') --institution @ExtraArgs }
        'status' { & $institutionPython (Join-Path $institutionRoot 'gleanera_cli.py') status @ExtraArgs }
        'download' { & $institutionPython (Join-Path $institutionRoot 'gleanera_cli.py') cnki --session-mode institution @ExtraArgs }
        'list' { & $institutionPython (Join-Path $institutionRoot 'gleanera_cli.py') cnki-list --session-mode institution @ExtraArgs }
        'test' { Push-Location $institutionRoot; try { & $institutionPython -m pytest -q @ExtraArgs } finally { Pop-Location } }
    }
    if ($LASTEXITCODE -ne 0) { throw "机构旁路执行失败，退出码 $LASTEXITCODE；请检查日志。" }
}
finally {
    $env:GLEANERA_ROOT = $savedRoot
    $env:GLEANERA_PYTHON = $savedPython
    $env:ACQ_BROWSER_CHANNEL = $savedChannel
}
