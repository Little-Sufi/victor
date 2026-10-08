# 🎮 Host Automation & Gaming Control

VICTOR possesses native host operating system capabilities, allowing him to act as an in-game co-pilot, keyboard operator, and terminal controller.

---

## 🕹️ Gaming Macro Engine

VICTOR executes complex, timed keystroke combos without blocking conversational voice streaming:

### 1. `execute_game_macro(sequence)`
Executes timed key presses defined as comma-separated key/duration pairs:
```text
"w:2.0,shift+w:1.0,space:0.5"
```
* **Use Cases**: Sprinting across map terrain, dodging in RPGs, automated gear shifts in racing simulators (NFS, Forza).

### 2. `hold_key(key, duration_seconds)`
Maintains a pressed key state for the specified duration before releasing:
```python
hold_key("w", duration_seconds=5.0)  # Continuous forward movement
```

---

## ⌨️ Desktop & Terminal Automation

* **Cursor Navigation**: `navigate_cursor(direction, words=1)` jumps the editing cursor across source code lines.
* **Text Selection**: `select_text(direction, count=1)` selects text blocks by character, word, or line.
* **Screen Clicking**: `click_at(x, y, button="left")` performs normalized coordinates clicks on any desktop window.
* **Background Tasks**: `start_background_task(command)` spawns asynchronous background workers for compilers, tests, and network jobs.
