# 停止现有 Python 进程
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

# 启动后端服务
$backendPath = 'C:\Users\Administrator\Desktop\TraceBack\backend'
Set-Location $backendPath
Start-Process python -ArgumentList 'run.py' -WindowStyle Hidden

Write-Host 'Backend service restarted'
