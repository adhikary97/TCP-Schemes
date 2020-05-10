set UnixPath to POSIX path of ((path to me as text) & "::")

tell application "Terminal"
    do script "python3 " & UnixPath & "receiver.py 127.0.0.1 5000 1"
end tell

delay 1

tell application "Terminal"
  do script "python3 " & UnixPath & "sender.py 127.0.0.1 5000 127.0.0.1 3000 " & UnixPath & "sender.py 1"
end tell
