@echo off
chcp 65001
:: 设置编码为 UTF-8，确保中文显示正常

:: 更新.bat - 自动从远程仓库拉取最新代码

:: 设置远程仓库地址和分支
set REMOTE_REPO=https://gitee.com/icecloudly/dice-pp-pear-dice-new-version.git
set BRANCH=master

:: 切换到脚本所在目录
cd /d %~dp0

:: 确保当前目录是 Git 仓库
if not exist .git (
    echo 当前目录不是 Git 仓库，请检查！
    pause
    exit /b 1
)

:: 拉取最新代码
echo 正在从远程仓库拉取最新代码...
git fetch %REMOTE_REPO% %BRANCH%
git reset --hard FETCH_HEAD

echo 更新完成！
pause