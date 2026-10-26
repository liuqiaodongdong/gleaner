param([Parameter(ValueFromRemainingArguments = $true)]$CliArgs)

function Find-GleanerRoot {
    if ($env:GLEANERA_ROOT) {
        return $env:GLEANERA_ROOT
    }
    $skillDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
    $marker = Join-Path $skillDir ".gleanera_root"
    if (Test-Path -LiteralPath $marker) {
        $pointed = (Get-Content -LiteralPath $marker -Encoding UTF8 -Raw).Trim()
        if ($pointed -and (Test-Path (Join-Path $pointed "gleanera_cli.py"))) {
            return $pointed
        }
    }
    # 仓库内：skill/gleanera/scripts → 仓库根
    $candidate = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
    if (Test-Path (Join-Path $candidate "gleanera_cli.py")) {
        return $candidate
    }
    throw @"
未找到 gleaner 仓库（没有 GLEANERA_ROOT，也没有 .gleanera_root）。请先：
  python `"$PSScriptRoot\bootstrap.py`"
或：
  git clone --branch feature/cnki-institution-session --single-branch https://github.com/liuqiaodongdong/gleaner.git gleanera
  cd gleanera
  python -m pip install -r requirements.txt
  python gleanera_cli.py install-skill
"@
}

$Root = Find-GleanerRoot
$py = if ($env:GLEANERA_PYTHON) { $env:GLEANERA_PYTHON } else { "python" }
Set-Location $Root
& $py (Join-Path $Root "gleanera_cli.py") @CliArgs
exit $LASTEXITCODE
