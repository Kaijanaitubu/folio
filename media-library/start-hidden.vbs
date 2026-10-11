Option Explicit
Dim files, shell, launcher, command, args
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
launcher = files.BuildPath(files.GetParentFolderName(WScript.ScriptFullName), "run-background.ps1")
args = ""
If WScript.Arguments.Count > 0 Then
    If Not IsNumeric(WScript.Arguments(0)) Then WScript.Quit 1
    args = " -Port " & CInt(WScript.Arguments(0))
End If
command = """" & shell.ExpandEnvironmentStrings("%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe") & """ -NoProfile -NonInteractive -WindowStyle Hidden -File """ & launcher & """" & args
' Window style 0 prevents a console window from appearing at sign-in.
shell.Run command, 0, False
