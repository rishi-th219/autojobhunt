' run_daemon_background.vbs — Silent Background Launcher for AutoJobHunt Daemon
' Runs background_daemon.py with completely hidden console window on Windows.

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
strPython = "python.exe"

' Check if conda python exists
strCondaPy = WshShell.ExpandEnvironmentStrings("%USERPROFILE%") & "\miniconda3\python.exe"
If fso.FileExists(strCondaPy) Then
    strPython = strCondaPy
End If

strCommand = """" & strPython & """ """ & strScriptDir & "\background_daemon.py"""
WshShell.Run strCommand, 0, False
Set WshShell = Nothing
Set fso = Nothing
