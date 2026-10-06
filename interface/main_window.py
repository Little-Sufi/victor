"""
VICTOR Interface - Advanced Glowing Orb
A dynamic, animated, futuristic 3D orb interface.
"""
import sys
import os
from pathlib import Path
import math
import random

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QApplication, QSystemTrayIcon, QMenu, QGraphicsDropShadowEffect
)
from PySide6.QtCore import (
    Qt, QTimer, QPoint, QPointF, Signal, QThread
)
from PySide6.QtGui import (
    QFont, QColor, QPainter, QRadialGradient, QConicalGradient, QBrush, QPen, QMouseEvent, QAction, QIcon
)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.victor_core import VictorCore, VictorState


class ListenWorker(QThread):
    """Worker thread for click-to-speak (one-shot listen)."""
    result_ready = Signal(str)

    def __init__(self, victor):
        super().__init__()
        self.victor = victor

    def run(self):
        result = self.victor.listen_once()
        self.result_ready.emit(result if result else "")


class VictorOrb(QWidget):
    """Advanced Dynamic Orb Interface for VICTOR."""
    
    # Thread-safe signals for cross-thread GUI updates
    wake_word_signal = Signal()
    speak_signal = Signal(str)
    state_change_signal = Signal(object)
    thought_signal = Signal(str)

    def __init__(self):
        super().__init__()
        
        self.victor = None
        self.drag_position = None
        self._listen_worker = None
        
        # Animation state variables
        self.phase = 0.0
        self.base_radius = 65
        self.pulse_radius = 0
        
        # State Colors
        self.color_idle = QColor(0, 212, 255)      # Cyan
        self.color_listening = QColor(48, 209, 88) # Bright Green
        self.color_thinking = QColor(191, 90, 242) # Electric Purple
        self.color_speaking = QColor(10, 132, 255) # Deep Blue
        
        self.current_color = self.color_idle
        self.target_color = self.color_idle
        
        self._setup_window()
        self._setup_ui()
        self._setup_system_tray()
        
        # Connect signals to slots (thread-safe)
        self.state_change_signal.connect(self._on_state_change)
        self.thought_signal.connect(self._on_thought)
        self.wake_word_signal.connect(self._on_wake_word)
        self.speak_signal.connect(self._handle_speak)
        
        # Animation Timer (Smooth 60fps ~ 16ms)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(16)
        
        self._init_victor()

    def _setup_window(self):
        self.setWindowTitle("VICTOR")
        self.setFixedSize(380, 420)
        
        # Frameless, transparent, always on top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - 380) // 2,
            (screen.height() - 420) // 2
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        # Push the label down below the orb
        layout.setContentsMargins(20, 260, 20, 20)
        
        # Subtitle / Status Label
        self.subtitle_label = QLabel("Initializing Systems...")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet("""
            color: rgba(255, 255, 255, 200);
            font-family: 'Segoe UI', 'Helvetica Neue', sans-serif;
            font-size: 14px;
            font-weight: 500;
            background-color: rgba(15, 15, 20, 150);
            border: 1px solid rgba(255, 255, 255, 20);
            border-radius: 15px;
            padding: 12px 18px;
        """)
        
        # Drop shadow for text readability and aesthetic depth
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 180))
        shadow.setOffset(0, 5)
        self.subtitle_label.setGraphicsEffect(shadow)
        
        layout.addWidget(self.subtitle_label)

    def _init_victor(self):
        class InitWorker(QThread):
            finished = Signal(object)
            def run(self):
                v = VictorCore()
                self.finished.emit(v)

        self.init_thread = InitWorker()
        self.init_thread.finished.connect(self._on_victor_ready)
        self.init_thread.start()

    def _on_victor_ready(self, victor: VictorCore):
        self.victor = victor
        
        # Wire up callbacks — use signals for thread safety
        # (always-on mic runs in a background thread, GUI must update on main thread)
        self.victor.on_state_change = lambda state: self.state_change_signal.emit(state)
        self.victor.on_thought = lambda text: self.thought_signal.emit(text)
        self.victor.on_wake_word_detected = lambda: self.wake_word_signal.emit()
        self.victor.on_speak = lambda text: self.speak_signal.emit(text)
        
        # Start always-on voice mode — mic is now permanently active
        self.victor.start_voice_mode()
        
        self.subtitle_label.setText("VICTOR Online\n🎤 Always listening — say 'Hey VICTOR'")
        self.target_color = self.color_idle
        
        # Show the orb now that Victor is ready
        self.show()
        self.activateWindow()
        self.raise_()

    def _handle_speak(self, text: str):
        """Handle speak signal — runs TTS in a thread to not block GUI."""
        if self.victor and self.victor.voice:
            self.victor.voice.speak(text, block=False)

    def _on_wake_word(self):
        """Flash the orb green when wake word is heard."""
        self.subtitle_label.setText("🎤 Heard you!")
        self.target_color = self.color_listening
        self.show()
        self.activateWindow()
        self.raise_()

    def _on_state_change(self, state: VictorState):
        if state.listening and not state.processing and not state.speaking:
            self.subtitle_label.setText("🎤 Listening...")
            self.target_color = self.color_listening
        elif state.processing:
            self.subtitle_label.setText("🧠 Thinking...")
            self.target_color = self.color_thinking
        elif state.speaking:
            self.subtitle_label.setText("🔊 Speaking...")
            self.target_color = self.color_speaking
        else:
            self.subtitle_label.setText("Online\n🎤 Say 'Hey VICTOR'")
            self.target_color = self.color_idle

    def _on_thought(self, thought: str):
        display_text = thought.replace('[Thought]', '').strip()
        if len(display_text) > 100:
            display_text = display_text[:97] + "..."
        self.subtitle_label.setText(display_text)

    def _animate(self):
        # Time progression
        dt = 0.05
        self.phase += dt
        
        # Smooth Color Interpolation
        r = int(self.current_color.red() + (self.target_color.red() - self.current_color.red()) * 0.05)
        g = int(self.current_color.green() + (self.target_color.green() - self.current_color.green()) * 0.05)
        b = int(self.current_color.blue() + (self.target_color.blue() - self.current_color.blue()) * 0.05)
        self.current_color = QColor(r, g, b)
        
        # Dynamic pulse radius based on state
        if self.victor:
            if self.victor.state.listening:
                self.pulse_radius = math.sin(self.phase * 3) * 12
                self.phase += 0.05 # Speed up phase
            elif self.victor.state.processing:
                self.pulse_radius = math.sin(self.phase * 4) * 8
                self.phase += 0.1 # Fast phase
            elif self.victor.state.speaking:
                self.pulse_radius = math.sin(self.phase * 5) * 15 + random.uniform(-4, 4)
                self.phase += 0.08
            else:
                # Idle breathing
                self.pulse_radius = math.sin(self.phase * 0.8) * 4
        else:
            self.pulse_radius = math.sin(self.phase * 0.8) * 4
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Orb Center
        center = QPointF(self.width() / 2.0, 140.0)
        current_radius = self.base_radius + self.pulse_radius
        
        # Extract base colors for gradients
        cr = self.current_color.red()
        cg = self.current_color.green()
        cb = self.current_color.blue()
        
        # =========================================================================
        # 1. AMBIENT OUTER GLOW
        # =========================================================================
        painter.save()
        glow_radius = current_radius + 90
        glow_grad = QRadialGradient(center, glow_radius)
        glow_grad.setColorAt(0.0, QColor(cr, cg, cb, 0))
        glow_grad.setColorAt(0.4, QColor(cr, cg, cb, 15))
        glow_grad.setColorAt(0.7, QColor(cr, cg, cb, 5))
        glow_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
        painter.setBrush(glow_grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, glow_radius, glow_radius)
        painter.restore()
        
        # =========================================================================
        # 2. THE MAIN GLASS ORB BODY
        # =========================================================================
        painter.save()
        main_grad = QRadialGradient(center, current_radius)
        # Deep translucent core
        main_grad.setColorAt(0.0, QColor(255, 255, 255, 220))
        main_grad.setColorAt(0.3, QColor(cr, cg, cb, 180))
        main_grad.setColorAt(0.7, QColor(cr, cg, cb, 80))
        main_grad.setColorAt(0.9, QColor(min(cr+50, 255), min(cg+50, 255), min(cb+50, 255), 160)) # Edge highlight
        main_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
        painter.setBrush(main_grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, current_radius, current_radius)
        painter.restore()

        # =========================================================================
        # 3. ROTATING ENERGY RINGS
        # =========================================================================
        # Ring 1
        painter.save()
        ring1_radius = current_radius + 8
        ring1_grad = QConicalGradient(center, math.degrees(self.phase))
        ring1_grad.setColorAt(0.0, QColor(cr, cg, cb, 0))
        ring1_grad.setColorAt(0.2, QColor(255, 255, 255, 200))
        ring1_grad.setColorAt(0.5, QColor(cr, cg, cb, 100))
        ring1_grad.setColorAt(0.8, QColor(255, 255, 255, 200))
        ring1_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
        
        pen1 = QPen(ring1_grad, 2.0)
        pen1.setCapStyle(Qt.RoundCap)
        painter.setPen(pen1)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, ring1_radius, ring1_radius)
        painter.restore()

        # Ring 2 (Counter-rotating, slightly larger, variable based on state)
        if self.victor and (self.victor.state.processing or self.victor.state.listening):
            painter.save()
            ring2_radius = current_radius + 18
            ring2_grad = QConicalGradient(center, -math.degrees(self.phase * 1.5))
            ring2_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
            ring2_grad.setColorAt(0.3, QColor(cr, cg, cb, 180))
            ring2_grad.setColorAt(0.7, QColor(cr, cg, cb, 180))
            ring2_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
            
            pen2 = QPen(ring2_grad, 1.0)
            painter.setPen(pen2)
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(center, ring2_radius, ring2_radius)
            painter.restore()
        
        # =========================================================================
        # 4. INNER ENERGY CORE (Pulsating intensely when speaking)
        # =========================================================================
        if self.victor and self.victor.state.speaking:
            painter.save()
            core_radius = current_radius * 0.4 + random.uniform(0, 5)
            core_grad = QRadialGradient(center, core_radius)
            core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            core_grad.setColorAt(0.5, QColor(cr, cg, cb, 200))
            core_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
            painter.setBrush(core_grad)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, core_radius, core_radius)
            painter.restore()

        painter.end()

    # --- Mouse Interaction ---
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._is_drag = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            self._is_drag = True
            event.accept()
            
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if not getattr(self, '_is_drag', False):
                self._click_to_speak()
            self._is_drag = False
            
    def contextMenuEvent(self, event):
        """Right click menu."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1a1a2e; color: #00d4ff; border: 1px solid #00d4ff; border-radius: 5px;}
            QMenu::item { padding: 5px 20px; }
            QMenu::item:selected { background-color: #00d4ff; color: #000000; }
        """)
        
        diag_act = QAction("Diagnostics", self)
        diag_act.triggered.connect(lambda: self._on_thought(self.victor.self_diagnose() if self.victor else "Not ready"))
        menu.addAction(diag_act)

        hide_act = QAction("Hide", self)
        hide_act.triggered.connect(self.hide_to_background)
        menu.addAction(hide_act)

        exit_act = QAction("Shutdown VICTOR", self)
        exit_act.triggered.connect(self._quit)
        menu.addAction(exit_act)
        
        menu.exec_(event.globalPos())

    def _click_to_speak(self):
        """Click the orb to do a one-shot listen (in addition to always-on)."""
        if not self.victor:
            return
            
        self.show()
        self.activateWindow()
        self.raise_()
        
        # Stop any current speech
        if self.victor.voice:
            self.victor.voice.stop_speaking()
            
        # If a listen worker is already running, cancel it
        if self._listen_worker and self._listen_worker.isRunning():
            try:
                self._listen_worker.terminate()
                self._listen_worker.wait(200)
            except:
                pass
                
            self.victor.state.listening = False
            self.victor.state.processing = False
            self.victor.state.speaking = False
            self._on_state_change(self.victor.state)

        # Temporarily pause always-on so they don't conflict
        was_always_on = self.victor.voice._always_on
        if was_always_on:
            self.victor.voice.stop_always_on()

        self.subtitle_label.setText("🎤 Listening (click)...")
        self.target_color = self.color_listening

        self._listen_worker = ListenWorker(self.victor)

        def on_result(r):
            if r:
                display = r[:100] + ("..." if len(r) > 100 else "")
                self.subtitle_label.setText(display)
            else:
                self.subtitle_label.setText("Online\n🎤 Say 'Hey VICTOR'")
            self.target_color = self.color_idle
            # Restart always-on after click-to-speak finishes
            if was_always_on:
                self.victor.start_voice_mode()

        self._listen_worker.result_ready.connect(on_result)
        self._listen_worker.start()

    def _setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        from PySide6.QtWidgets import QStyle
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        tray_menu = QMenu()
        show_action = QAction("Show Victor", self)
        show_action.triggered.connect(self.show_from_background)
        hide_action = QAction("Hide to Background", self)
        hide_action.triggered.connect(self.hide_to_background)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
        
        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def hide_to_background(self):
        self.hide()
        self.subtitle_label.setText("Running in Background")

    def show_from_background(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def _quit(self):
        if self.victor:
            self.victor.shutdown()
        self.tray_icon.hide()
        QApplication.quit()

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    window = VictorOrb()
    window.show()
    
    sys.exit(app.exec())
