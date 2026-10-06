Set WshShell = CreateObject("WScript.Shell")

' Get the directory where this VBS script lives
strScriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Set working directory to the script's folder
WshShell.CurrentDirectory = strScriptDir

' Use the venv Python if available, otherwise fall back to system Python
strVenvPython = strScriptDir & "\.venv\Scripts\pythonw.exe"
Set fso = CreateObject("Scripting.FileSystemObject")

If fso.FileExists(strVenvPython) Then
    WshShell.Run """" & strVenvPython & """ main.py", 0, False
Else
    WshShell.Run "pythonw.exe main.py", 0, False
End If
