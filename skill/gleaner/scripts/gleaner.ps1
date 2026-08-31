param([Parameter(ValueFromRemainingArguments = $true)]$CliArgs)

function Find-GleanerRoot {
    if ($env:GLEANER_ROOT) {
        return $env:GLEANER_ROOT
    }
    $skillDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $marker = Join-Path $skillDir ".gleaner_root"
    if (Test-Path -LiteralPath $marker) {
        $pointed = (Get-Content -LiteralPath $marker -Encoding UTF8 -Raw).Trim()
        if ($pointed -and (Test-Path (Join-Path $pointed "gleaner_cli.py"))) {
            return $pointed
        }
    }
    # 仓库内：skill/gleaner/scripts → 仓库根
    $candidate = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
    if (Test-Path (Join-Path $candidate "gleaner_cli.py")) {
        return $candidate
    }
    throw @"
未找到 gleaner 仓库（没有 GLEANER_ROOT，也没有 .gleaner_root）。请先：
  git clone https://github.com/liuqiaodongdong/gleaner.git
  cd gleaner
  python -m pip install -r requirements.txt
  python gleaner_cli.py install-skill
或把 GLEANER_ROOT 设为含 gleaner_cli.py 的仓库根。
"@
}

$Root = Find-GleanerRoot
$py = if ($env:GLEANER_PYTHON) { $env:GLEANER_PYTHON } else { "python" }
Set-Location $Root
& $py (Join-Path $Root "gleaner_cli.py") @CliArgs
exit $LASTEXITCODE
