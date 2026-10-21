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
    throw '请先在此工作目录创建 .venv 并安装 requirements.txt。'
}
$savedRoot = $env:GLEANER_ROOT
$savedPython = $env:GLEANER_PYTHON
$savedChannel = $env:ACQ_BROWSER_CHANNEL
try {
    $env:GLEANER_ROOT = $institutionRoot
    $env:GLEANER_PYTHON = $institutionPython
    if (-not $env:ACQ_BROWSER_CHANNEL) { $env:ACQ_BROWSER_CHANNEL = 'msedge' }
    switch ($Action) {
        'login' { & $institutionPython (Join-Path $institutionRoot 'login.py') --institution @ExtraArgs }
        'status' { & $institutionPython (Join-Path $institutionRoot 'gleaner_cli.py') status @ExtraArgs }
        'download' { & $institutionPython (Join-Path $institutionRoot 'gleaner_cli.py') cnki --session-mode institution @ExtraArgs }
        'list' { & $institutionPython (Join-Path $institutionRoot 'gleaner_cli.py') cnki-list --session-mode institution @ExtraArgs }
        'test' { Push-Location $institutionRoot; try { & $institutionPython -m pytest -q @ExtraArgs } finally { Pop-Location } }
    }
    if ($LASTEXITCODE -ne 0) { throw "机构旁路执行失败，退出码 $LASTEXITCODE；请检查日志。" }
}
finally {
    $env:GLEANER_ROOT = $savedRoot
    $env:GLEANER_PYTHON = $savedPython
    $env:ACQ_BROWSER_CHANNEL = $savedChannel
}
