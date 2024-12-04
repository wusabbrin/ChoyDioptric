:: This file may have to be tweaked for your specific PC. Just consider it a starting point. 
@REM start cmd /k manager\scalabrad-0.8.3\bin\labrad.bat
start cmd /k "C:\Users\choyl\ChoyDioptric\manager\scalabrad-0.8.3\bin\labrad.bat"
start cmd /k manager\scalabrad-web-server-2.0.5\bin\labrad-web.bat
start "" "C:\Users\choyl\ChoyDioptric\chrome\chrome.exe" /new-window http://localhost:7667
call "C:\ProgramData\anaconda3\Scripts\activate.bat" dioptric
call python -m labrad.node
