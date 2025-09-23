@echo off
chcp 65001 >nul
REM ================================
REM DicePP 启动脚本 (自动安装依赖 + 失败诊断)
REM 1) 首次运行自动安装 requirements.txt (含 python-docx)
REM 2) 若打包自带依赖，可放一个 .deps_installed 避免安装
REM 3) 若安装失败，会在 install.log 中留下记录并停留窗口
REM 可选参数：
REM   /reinstall   强制重新安装依赖
REM   /skipinstall  跳过依赖检测 (调试用)
REM   /quiet        静默模式：不直接输出 bot 日志，写入 runtime.log 并循环重启
REM   /once         只运行一次 bot.py（与 /quiet 可组合）
REM   /debug        开启命令逐行回显（通常不需要，/quiet 时仍会重定向日志）
REM ================================
Title DicePP 启动中 - v1.4.2

setlocal enabledelayedexpansion
set GIT_PYTHON_REFRESH=quiet
set BASE_DIR=%~dp0
set PYTHON_EXE=..\Python\python.exe
set LOG_FILE=%BASE_DIR%install.log
set FLAG_FILE=%BASE_DIR%.deps_installed
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set FAIL_COUNT=0
set QUICK_EXIT_THRESHOLD=8

REM 解析简单参数
set ARG_REINSTALL=0
set ARG_SKIP=0
set ARG_DEBUG=0
set ARG_ONCE=0
set ARG_QUIET=0
for %%A in (%*) do (
	if /i "%%A"=="/reinstall"  set ARG_REINSTALL=1
	if /i "%%A"=="-reinstall"  set ARG_REINSTALL=1
	if /i "%%A"=="/skipinstall" set ARG_SKIP=1
	if /i "%%A"=="-skipinstall" set ARG_SKIP=1
	if /i "%%A"=="/debug"      set ARG_DEBUG=1
	if /i "%%A"=="-debug"      set ARG_DEBUG=1
	if /i "%%A"=="/quiet"      set ARG_QUIET=1
	if /i "%%A"=="-quiet"      set ARG_QUIET=1
		if /i "%%A"=="/once"       set ARG_ONCE=1
		if /i "%%A"=="-once"       set ARG_ONCE=1
)

if %ARG_DEBUG%==1 (
	echo [DEBUG] 调试模式已开启
	echo on
)

REM 选择 Python 解释器 (优先使用上级目录便携版，其次系统 PATH)
set "PY_CMD="
if exist "%PYTHON_EXE%" set "PY_CMD=%PYTHON_EXE%"
if not defined PY_CMD (
	for /f "delims=" %%i in ('where python 2^>nul') do set "PY_CMD=python"
)
if not defined PY_CMD (
	echo [错误] 未找到 Python。
	echo 解决方法之一：
	echo   1. 在系统安装官方 Python 并勾选 Add to PATH；或
	echo   2. 在 DicePPBOT 目录放置 Python 便携版到 "Python" 文件夹，其内含 python.exe
	pause
	exit /b 3
)
echo 使用 Python: %PY_CMD%

REM 若为嵌入式发行版，自动确保启用 site 模块（否则 pip 安装的包无法被发现）
for %%P in (36 37 38 39 310 311 312) do (
	if exist "..\Python\python%%P._pth" (
		set EMBED_PTH=..\Python\python%%P._pth
	)
)
if defined EMBED_PTH (
	findstr /i "import site" "%EMBED_PTH%" >nul 2>&1
	if errorlevel 1 (
		echo [信息] 检测到嵌入式 Python，自动在 %EMBED_PTH% 末尾追加 "import site"
		echo import site>>"%EMBED_PTH%"
	) else (
		echo [信息] 已启用 site: %EMBED_PTH%
	)
)

REM ===== 依赖检查（使用线性 IF + GOTO，避免多层括号导致解析问题）
if %ARG_SKIP%==1 (
	echo [提示] 已指定 /skipinstall，跳过依赖安装检查。
	goto :run
)
if not exist "%BASE_DIR%requirements.txt" (
	echo [警告] 未找到 requirements.txt，跳过依赖安装。
	goto :run
)
if %ARG_REINSTALL%==1 (
	echo [信息] 强制重新安装依赖...
	del /f /q "%FLAG_FILE%" >nul 2>&1
	goto :do_install
)
if not exist "%FLAG_FILE%" goto :do_install
echo 依赖已安装 (如需重装: DicePP.bat /reinstall)
goto :run

:do_install
echo ================================
echo 正在安装/更新依赖 (可能需要几分钟)...
echo 详细输出写入: %LOG_FILE%
echo ================================
echo [1/3] 检测 pip ...
"%PY_CMD%" -m pip --version >nul 2>&1
if errorlevel 1 (
	echo 未检测到 pip，尝试使用 ensurepip 初始化...>>"%LOG_FILE%"
	"%PY_CMD%" -m ensurepip --default-pip >>"%LOG_FILE%" 2>&1
)

echo [2/3] 升级 pip ...
"%PY_CMD%" -m pip install --upgrade pip >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
	echo [错误] pip 升级失败，请查看 install.log。
	goto :install_fail
)

echo [3/3] 安装 requirements.txt ...
"%PY_CMD%" -m pip install -r "%BASE_DIR%requirements.txt" >>"%LOG_FILE%" 2>&1
if errorlevel 1 (
	echo [错误] 依赖安装失败，请查看 install.log。
	goto :install_fail
)
echo success>"%FLAG_FILE%"
echo 依赖安装完成。
goto :run

:install_fail
echo.
echo --------------------------------------------------
echo 安装失败，请根据 install.log 内容排查：
echo 常见原因：
echo  1. 无网络或被代理阻断
echo  2. Python 未安装 VC 运行库 (针对部分编译型依赖)
echo  3. 权限不足 (尝试管理员方式)
echo  4. 国内网络波动，可多试几次或换镜像源
echo --------------------------------------------------
echo (窗口不会自动关闭，按任意键退出)
pause >nul
exit /b 1

:run
echo.
echo 启动 DicePP 中...
set RUNTIME_LOG=%BASE_DIR%runtime.log
if %ARG_QUIET%==1 echo [INFO] 静默模式: 日志写入 %RUNTIME_LOG%
REM ===== 端口检测与自动回退 =====
set DESIRED_PORT=8080
for %%P in (8080 8081 8082 8090 9000) do (
	powershell -NoProfile -Command "try{(Get-NetTCPConnection -State Listen -LocalPort %%P -ErrorAction Stop)|Out-Null;$busy=$true}catch{$busy=$false}; if($busy){exit 1}else{exit 0}" >nul 2>&1
	if not errorlevel 1 (
		set DESIRED_PORT=%%P
		goto :port_found
	)
)
:port_found
if not "%DESIRED_PORT%"=="8080" (
	echo [INFO] Port 8080 is busy. Using available port %DESIRED_PORT%.
)
REM 若 .env.prod 中写死 8080，提前以环境变量覆写
set PORT=%DESIRED_PORT%
if %ARG_DEBUG%==1 echo [DEBUG] 最终使用端口 PORT=%PORT%
if %ARG_QUIET%==1 (
	echo [INFO] 静默运行 端口=%DESIRED_PORT% 日志=%RUNTIME_LOG%  (去掉 /quiet 查看实时输出)
) else (
	echo [INFO] 前台运行 端口=%DESIRED_PORT% 直接输出日志 (Ctrl+C 停止)
)

REM ===== 关键依赖快速验证 (即使标记已存在也补装缺失包) =====
"%PY_CMD%" -c "import docx" >nul 2>&1
if errorlevel 1 (
	echo [INFO] 检测到缺失 python-docx，正在自动安装...
	"%PY_CMD%" -m pip install python-docx lxml >nul 2>&1
	if errorlevel 1 (
		echo [WARN] 自动安装 python-docx 失败，可手动执行: %PY_CMD% -m pip install python-docx
	) else (
		echo [INFO] 已补充安装 python-docx。
	)
)

REM 主循环
:start
REM 记录启动时间 (100ns 单位)
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToFileTimeUtc()"') do set START_TICKS=%%i
if %ARG_QUIET%==1 if %ARG_DEBUG%==1 (
  echo [DEBUG] ===== 新一轮启动 ===== >>"%RUNTIME_LOG%"
  echo [DEBUG] 时间: %date% %time% >>"%RUNTIME_LOG%"
)
if %ARG_QUIET%==1 (
  "%PY_CMD%" bot.py >>"%RUNTIME_LOG%" 2>&1
) else (
  "%PY_CMD%" bot.py
)
set RET=%ERRORLEVEL%
REM 记录结束时间并计算运行秒数
for /f %%i in ('powershell -NoProfile -Command "(Get-Date).ToFileTimeUtc()"') do set END_TICKS=%%i
for /f %%i in ('powershell -NoProfile -Command "([int](($env:END_TICKS - $env:START_TICKS)/10000000))"') do set RUN_SECONDS=%%i
if "%RUN_SECONDS%"=="" set RUN_SECONDS=0
echo [INFO] 本次运行时长: %RUN_SECONDS% 秒 (返回码 %RET%)
if %RUN_SECONDS% LSS %QUICK_EXIT_THRESHOLD% (
	set /a FAIL_COUNT+=1
) else (
	set FAIL_COUNT=0
)
if %FAIL_COUNT% GEQ 3 (
	echo [ERROR] 连续 %FAIL_COUNT% 次在 %QUICK_EXIT_THRESHOLD% 秒内退出，暂停以便查看问题。查看 runtime.log 或使用 /debug。
	pause
	set FAIL_COUNT=0
)
if %ARG_QUIET%==1 if %ARG_DEBUG%==1 echo [DEBUG] bot.py 退出码=%RET% >>"%RUNTIME_LOG%"
if %RET%==9009 (
	echo [错误] 无法执行 %PY_CMD%，请确认已安装 Python。
	pause
	exit /b 2
)
if %RET% NEQ 0 (
	echo [警告] bot.py 异常退出，返回码 %RET% (日志见 runtime.log)
)
if %ARG_ONCE%==1 (
	echo [信息] /once 模式：单次运行结束 (返回码 %RET%)。按任意键退出。
	pause >nul
	exit /b %RET%
)
if %ARG_ONCE%==0 if %ARG_QUIET%==1 (
	if %ARG_DEBUG%==1 (
		echo [DEBUG] 5 秒后重启 (Ctrl+C 取消)
		timeout /t 5
	) else (
		echo 程序已退出，5 秒后自动重启 (/quiet 静默模式, /once 单次, Ctrl+C 取消)...
		timeout /t 5 >nul
	)
)
if %ARG_ONCE%==0 if %ARG_QUIET%==0 (
	echo 程序已退出。5 秒后重启 (Ctrl+C 取消 /quiet 静默 /once 单次)...
	timeout /t 5 >nul
)
if %ARG_ONCE%==1 (
	echo 运行结束。按任意键关闭窗口。
	pause >nul
	exit /b %RET%
)
goto start

REM 理论上不会到达这里，保险 pause
pause