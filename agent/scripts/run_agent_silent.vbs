' run_agent_silent.vbs
' Silent launcher for the UPSC Daily Agent.
' Uses WScript.Shell.Run with intWindowStyle=0 so NO CMD window appears.
' This is used by Windows Task Scheduler for silent background execution.

Option Explicit

Dim objShell, strProjectDir, strPythonCmd, strLogFile, strCmd

strProjectDir = "d:\project\agent"
strLogFile    = strProjectDir & "\agent_runs.log"

' Detect pythonw.exe (runs without console) vs python.exe as fallback
Dim objFSO
Set objFSO = CreateObject("Scripting.FileSystemObject")

' Try to find pythonw in PATH-adjacent locations
Dim strPython
strPython = "pythonw"  ' WScript will resolve via PATH

' Build the command: run main.py from the project directory, redirect output to log
strCmd = "cmd /c cd /d """ & strProjectDir & """ && python main.py >> """ & strLogFile & """ 2>&1"

' Timestamp the log
Dim objLog
Set objLog = objFSO.OpenTextFile(strLogFile, 8, True)  ' 8 = ForAppending, True = create if missing
objLog.WriteLine "[" & Now() & "] Silent VBS Launcher: Starting UPSC Agent Run"
objLog.Close

' Run with WindowStyle=0 (hidden), bWaitOnReturn=False (async)
Set objShell = CreateObject("WScript.Shell")
objShell.Run strCmd, 0, False

Set objShell = Nothing
Set objFSO = Nothing
