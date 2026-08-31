param([Parameter(ValueFromRemainingArguments = $true)]$CliArgs)

function Find-GleanerRoot {
    if ($env:GLEANER_ROOT) {
        return $env:GLEANER_ROOT
    }
    # 仓库内：skill/gleaner/scripts → 仓库根
    $candidate = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
    if (Test-Path (Join-Path $candidate "gleaner_cli.py")) {
        return $candidate
    }
    throw "未设置 GLEANER_ROOT，且无法从 Skill 位置找到 gleaner_cli.py。请把 GLEANER_ROOT 设为仓库根目录。"
}

$Root = Find-GleanerRoot
$py = if ($env:GLEANER_PYTHON) { $env:GLEANER_PYTHON } else { "python" }
Set-Location $Root
& $py (Join-Path $Root "gleaner_cli.py") @CliArgs
exit $LASTEXITCODE
