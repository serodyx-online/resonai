@echo off
echo ResonAI, kolay baslatici araciligiyla baslatiliyor...
:start
python resonai.py
echo Bot betigi %errorlevel% koduyla sonuc verdi.

if %errorlevel% == 5 (
    echo Yeniden baslatma sinyali alindi, 2 saniye icinde yeniden baslatiliyor...
    timeout /t 2 /nobreak > nul
    goto start
) else (
    echo Yeniden baslatma sinyali alinmadi, betik durduruluyor.
)
echo Baslatici komutu tamamlandi.
pause