@echo off
chcp 65001

rmdir /S /Q build 2>nul

python -m nuitka main.py ^
  --mode=standalone ^
  --msvc=latest ^
  --assume-yes-for-downloads ^
  --output-dir=build ^
  --remove-output ^
  --windows-console-mode=disable

xcopy assets build\main.dist\assets /E /I /Y
copy story.csv build\main.dist\story.csv /Y
if not exist build\main.dist\saves mkdir build\main.dist\saves

echo 完成：build\main.dist
pause