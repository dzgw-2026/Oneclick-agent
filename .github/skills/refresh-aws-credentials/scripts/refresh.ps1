param(
    [Parameter(Mandatory=$true)]
    [string]$AccessKeyId,

    [Parameter(Mandatory=$true)]
    [string]$SecretAccessKey,

    [Parameter(Mandatory=$true)]
    [string]$SessionToken,

    [string]$Region = "us-west-2"
)

# Refresh PATH to ensure aws CLI is available
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "Updating AWS credentials..." -ForegroundColor Cyan

aws configure set aws_access_key_id $AccessKeyId
aws configure set aws_secret_access_key $SecretAccessKey
aws configure set aws_session_token $SessionToken
aws configure set region $Region

Write-Host "Verifying credentials..." -ForegroundColor Cyan
$identity = aws sts get-caller-identity 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "AWS credentials updated successfully!" -ForegroundColor Green
    Write-Host $identity
    Write-Host ""
    Write-Host "Next: Restart MCP servers in VS Code (Ctrl+Shift+P -> 'MCP: List Servers')" -ForegroundColor Yellow
} else {
    Write-Host "ERROR: Credentials verification failed." -ForegroundColor Red
    Write-Host $identity
    exit 1
}
