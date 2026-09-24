' ARMADA scheduler - fires every realm's due jobs. Runs hidden, no console.
'
' Deliberately names NO realm: a realm's schedule is its own commitment and does not pause
' because you are viewing a different realm in the app. With no folder given the scheduler ticks
' every realm ARMADA knows about, active one first. Name a folder to fire only that realm.
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\Work\Development\MATCAP"
sh.Run """D:\Work\Development\MATCAP\.venv\Scripts\pythonw.exe"" -m armada schedule --engine claude", 0, False
