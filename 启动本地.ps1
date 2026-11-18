$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$projectPython = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    & python -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw '请先安装 Python 3.11 后重试。' }
    & $projectPython -m pip install -r (Join-Path $projectRoot 'deploy/requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw '依赖安装失败，请检查网络后重新安装依赖。' }
}
$secretPath = Join-Path $projectRoot '.secrets/ark.key'
if (Test-Path -LiteralPath $secretPath) {
    $encryptedKey = (Get-Content -Raw -LiteralPath $secretPath).Trim() | ConvertTo-SecureString
    $env:ARK_API_KEY = [Net.NetworkCredential]::new('', $encryptedKey).Password
}
$falSecretPath = Join-Path $projectRoot '.secrets/fal.key'
if (Test-Path -LiteralPath $falSecretPath) {
    $encryptedFalKey = (Get-Content -Raw -LiteralPath $falSecretPath).Trim() | ConvertTo-SecureString
    $env:FAL_KEY = [Net.NetworkCredential]::new('', $encryptedFalKey).Password
}
& $projectPython (Join-Path $projectRoot 'local/server.py') --port 8765
exit $LASTEXITCODE
