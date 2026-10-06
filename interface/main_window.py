"""
VICTOR Interface - Advanced Glowing Orb
A dynamic, animated, futuristic glowing orb interface powered by Gemini Live API.
Completely translucent (no square box), draggable, with energy rings and responsive states.
"""
import sys
import os
import math
import random
import threading
import asyncio
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QApplication, QSystemTrayIcon, QMenu, 
    QGraphicsDropShadowEffect, QStyle, QInputDialog, QLineEdit
)
from PySide6.QtCore import (
    Qt, QTimer, QPointF, Signal
)
from PySide6.QtGui import (
    QColor, QPainter, QRadialGradient, QConicalGradient, QPen, QMouseEvent, QAction
)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.gemini_live import VictorLiveAgent


class VictorOrb(QWidget):
    """Futuristic Floating Orb Interface for VICTOR."""
    
    # Thread-safe Qt signals
    status_signal = Signal(str)
    subtitle_signal = Signal(str)

    def __init__(self):
        super().__init__()
        
        self.agent = None
        self.agent_thread = None
        self.drag_position = None
        self._is_drag = False
        
        # Visual animation parameters
        self.phase = 0.0
        self.base_radius = 70.0
        self.pulse_radius = 0.0
        
        # State Colors
        self.color_idle = QColor(0, 240, 255)       # Electric Cyan
        self.color_listening = QColor(48, 209, 88)  # Neon Green
        self.color_thinking = QColor(191, 90, 242)  # Holographic Purple
        self.color_speaking = QColor(10, 132, 255)  # Energetic Deep Blue
        
        self.current_color = self.color_idle
        self.target_color = self.color_idle
        self.current_state = "idle"
        
        self._setup_window()
        self._setup_ui()
        self._setup_system_tray()
        
        # Connect signals
        self.status_signal.connect(self._on_status_change)
        self.subtitle_signal.connect(self._on_subtitle_change)
        
        # Smooth 60fps render loop
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate)
        self.anim_timer.start(16)
        
        self._start_agent()

    def _setup_window(self):
        self.setWindowTitle("VICTOR")
        self.setFixedSize(400, 440)
        
        # Frameless, transparent, stays on top
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        
        # Center in screen
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - 400) // 2,
            (screen.height() - 440) // 2
        )

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 275, 20, 20)
        
        # Futuristic HUD Subtitle
        self.subtitle_label = QLabel("Initializing VICTOR...")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setWordWrap(True)
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 230);
                font-family: 'Segoe UI', 'Helvetica Neue', 'Arial', sans-serif;
                font-size: 13px;
                font-weight: 600;
                background-color: rgba(10, 12, 20, 190);
                border: 1px solid rgba(0, 240, 255, 60);
                border-radius: 16px;
                padding: 10px 18px;
            }
        """)
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 240, 255, 70))
        shadow.setOffset(0, 4)
        self.subtitle_label.setGraphicsEffect(shadow)
        
        layout.addWidget(self.subtitle_label)

    def _start_agent(self):
        """Starts VictorLiveAgent in a dedicated daemon thread."""
        def on_status(s):
            self.status_signal.emit(s)
            
        def on_subtitle(text):
            self.subtitle_signal.emit(text)

        self.agent = VictorLiveAgent(
            on_status_change=on_status,
            on_subtitle_change=on_subtitle
        )

        def run_loop():
            try:
                asyncio.run(self.agent.run())
            except Exception as e:
                print(f"[Victor Orb] Agent thread error: {e}")

        self.agent_thread = threading.Thread(target=run_loop, daemon=True)
        self.agent_thread.start()

    def _on_status_change(self, status: str):
        self.current_state = status
        if status == "listening":
            self.target_color = self.color_listening
        elif status == "thinking":
            self.target_color = self.color_thinking
        elif status == "speaking":
            self.target_color = self.color_speaking
        else: # idle
            self.target_color = self.color_idle

    def _on_subtitle_change(self, text: str):
        display_text = text.strip()
        if len(display_text) > 120:
            display_text = display_text[:117] + "..."
        self.subtitle_label.setText(display_text)

    def _animate(self):
        # Progress phase
        dt = 0.05
        self.phase += dt
        
        # Color interpolation
        r = int(self.current_color.red() + (self.target_color.red() - self.current_color.red()) * 0.08)
        g = int(self.current_color.green() + (self.target_color.green() - self.current_color.green()) * 0.08)
        b = int(self.current_color.blue() + (self.target_color.blue() - self.current_color.blue()) * 0.08)
        self.current_color = QColor(r, g, b)
        
        # Dynamic pulse radius based on state
        if self.current_state == "listening":
            self.pulse_radius = math.sin(self.phase * 3.5) * 10.0
            self.phase += 0.04
        elif self.current_state == "thinking":
            self.pulse_radius = math.sin(self.phase * 4.5) * 7.0
            self.phase += 0.08
        elif self.current_state == "speaking":
            self.pulse_radius = math.sin(self.phase * 5.5) * 14.0 + random.uniform(-2.5, 2.5)
            self.phase += 0.06
        else:
            # Idle smooth breathing
            self.pulse_radius = math.sin(self.phase * 1.0) * 4.0
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = QPointF(self.width() / 2.0, 145.0)
        current_radius = self.base_radius + self.pulse_radius
        
        cr = self.current_color.red()
        cg = self.current_color.green()
        cb = self.current_color.blue()
        
        # 1. AMBIENT GLOW (Diffused aura)
        painter.save()
        glow_radius = current_radius + 95.0
        glow_grad = QRadialGradient(center, glow_radius)
        glow_grad.setColorAt(0.0, QColor(cr, cg, cb, 0))
        glow_grad.setColorAt(0.4, QColor(cr, cg, cb, 25))
        glow_grad.setColorAt(0.7, QColor(cr, cg, cb, 10))
        glow_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
        painter.setBrush(glow_grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, glow_radius, glow_radius)
        painter.restore()
        
        # 2. GLASS SPHERE SHELL (Multi-layer gradient)
        painter.save()
        main_grad = QRadialGradient(center, current_radius)
        main_grad.setColorAt(0.0, QColor(255, 255, 255, 230))
        main_grad.setColorAt(0.3, QColor(cr, cg, cb, 190))
        main_grad.setColorAt(0.7, QColor(cr, cg, cb, 90))
        main_grad.setColorAt(0.9, QColor(min(cr+55, 255), min(cg+55, 255), min(cb+55, 255), 180))
        main_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
        painter.setBrush(main_grad)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center, current_radius, current_radius)
        painter.restore()

        # 3. OUTER ROTATING ENERGY RING 1
        painter.save()
        ring1_radius = current_radius + 10.0
        ring1_grad = QConicalGradient(center, math.degrees(self.phase * 1.2))
        ring1_grad.setColorAt(0.0, QColor(cr, cg, cb, 0))
        ring1_grad.setColorAt(0.25, QColor(255, 255, 255, 220))
        ring1_grad.setColorAt(0.5, QColor(cr, cg, cb, 120))
        ring1_grad.setColorAt(0.75, QColor(255, 255, 255, 220))
        ring1_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
        
        pen1 = QPen(ring1_grad, 2.2)
        pen1.setCapStyle(Qt.RoundCap)
        painter.setPen(pen1)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, ring1_radius, ring1_radius)
        painter.restore()

        # 4. COUNTER-ROTATING ENERGY RING 2
        painter.save()
        ring2_radius = current_radius + 20.0
        ring2_grad = QConicalGradient(center, -math.degrees(self.phase * 1.8))
        ring2_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        ring2_grad.setColorAt(0.3, QColor(cr, cg, cb, 160))
        ring2_grad.setColorAt(0.7, QColor(cr, cg, cb, 160))
        ring2_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        
        pen2 = QPen(ring2_grad, 1.4)
        painter.setPen(pen2)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center, ring2_radius, ring2_radius)
        painter.restore()

        # 5. INNER ENERGY CORE (Intense pulsing when active/speaking)
        if self.current_state in ["speaking", "thinking"]:
            painter.save()
            core_radius = current_radius * 0.45 + (random.uniform(-3, 3) if self.current_state == "speaking" else 0)
            core_grad = QRadialGradient(center, core_radius)
            core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
            core_grad.setColorAt(0.5, QColor(cr, cg, cb, 210))
            core_grad.setColorAt(1.0, QColor(cr, cg, cb, 0))
            painter.setBrush(core_grad)
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(center, core_radius, core_radius)
            painter.restore()

        painter.end()

    # --- Mouse Gestures & Window Movement ---
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
            if not self._is_drag:
                # Click gesture: toggle mute or interrupt speech
                self._on_orb_clicked()
            self._is_drag = False
            event.accept()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Double click opens quick text command prompt."""
        if event.button() == Qt.LeftButton:
            self._prompt_text_command()
            event.accept()

    def _on_orb_clicked(self):
        """Action when user taps/clicks the orb."""
        if not self.agent:
            return
        if self.agent.is_speaking:
            # Tap orb to silence / interrupt
            self.agent.is_speaking = False
            while not self.agent.audio_out_queue.empty():
                try:
                    self.agent.audio_out_queue.get_nowait()
                    self.agent.audio_out_queue.task_done()
                except:
                    break
            self.subtitle_label.setText("VICTOR: Silenced")
            self.target_color = self.color_idle
        else:
            # Tap orb to toggle mute
            self.agent.is_muted = not self.agent.is_muted
            if self.agent.is_muted:
                self.subtitle_label.setText("🎤 Mic Muted (Click orb to unmute)")
                self.target_color = QColor(255, 69, 58) # Red
            else:
                self.subtitle_label.setText("🎤 Mic Active — speak freely")
                self.target_color = self.color_idle

    def _prompt_text_command(self):
        """Opens a dialog to send a text command directly to Victor."""
        text, ok = QInputDialog.getText(
            self, "VICTOR Command", "Enter message or command for VICTOR:",
            QLineEdit.Normal, ""
        )
        if ok and text.strip() and self.agent:
            self.agent.send_text(text.strip())

    def contextMenuEvent(self, event):
        """Right-click menu for quick actions."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #0b0e14;
                color: #00f0ff;
                border: 1px solid #00f0ff;
                border-radius: 8px;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #00f0ff;
                color: #000000;
            }
        """)

        cmd_act = QAction("💬 Send Command...", self)
        cmd_act.triggered.connect(self._prompt_text_command)
        menu.addAction(cmd_act)

        menu.addSeparator()

        mute_text = "Unmute Mic" if (self.agent and self.agent.is_muted) else "Mute Mic"
        mute_act = QAction(mute_text, self)
        mute_act.triggered.connect(self._on_orb_clicked)
        menu.addAction(mute_act)

        hide_act = QAction("Hide to Tray", self)
        hide_act.triggered.connect(self.hide_to_background)
        menu.addAction(hide_act)

        menu.addSeparator()

        exit_act = QAction("Shutdown VICTOR", self)
        exit_act.triggered.connect(self._quit)
        menu.addAction(exit_act)

        menu.exec(event.globalPos())

    def _setup_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        
        tray_menu = QMenu()
        show_action = QAction("Show Victor", self)
        show_action.triggered.connect(self.show_from_background)
        hide_action = QAction("Hide to Tray", self)
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

    def show_from_background(self):
        self.show()
        self.activateWindow()
        self.raise_()

    def _quit(self):
        if self.agent:
            self.agent.stop()
        self.tray_icon.hide()
        QApplication.quit()
        os._exit(0)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    window = VictorOrb()
    window.show()
    window.raise_()
    window.activateWindow()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
