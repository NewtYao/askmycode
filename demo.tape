Output demo.gif

Set Shell "zsh"
Set FontSize 14
Set Width 900
Set Height 550
Set Theme "Dracula"
Set Padding 20
Set TypingSpeed 40ms
Set PlaybackSpeed 1

# Activate venv
Hide
Type "source .venv/bin/activate"
Enter
Sleep 500ms
Show

# Show the help
Type "askmycode --help"
Enter
Sleep 2s

# Index the project
Type "askmycode index ."
Enter
Sleep 4s

# First question
Type `askmycode ask "how does the indexer chunk files?"`
Enter
Sleep 6s

# Second question with sources
Type `askmycode ask "how is the API key stored?" --sources`
Enter
Sleep 6s

# Stats
Type "askmycode stats"
Enter
Sleep 2s

Sleep 3s
