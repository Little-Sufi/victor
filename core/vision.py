
"""
VICTOR Vision System
Comprehensive visual understanding:
- Real-time screen capture & analysis
- OCR (text recognition from screen/images)
- Object detection (YOLOv8, local)
- UI element detection and interaction
- Camera input processing
- Visual question answering (local LLaVA via Ollama)
"""
import os
import io
import shutil
import base64
import tempfile
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from PIL import Image, ImageGrab, ImageDraw, ImageFont
import cv2
import yaml

# Local imports - handle optional dependencies gracefully
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


@dataclass
class DetectedObject:
    """An object detected in an image."""
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    center: Tuple[int, int]


@dataclass
class UIElement:
    """A detected UI element (button, text field, etc.)."""
    element_type: str
    text: str
    bbox: Tuple[int, int, int, int]
    confidence: float


@dataclass
class ScreenState:
    """Complete understanding of current screen state."""
    timestamp: str
    active_window: str
    detected_objects: List[DetectedObject]
    ui_elements: List[UIElement]
    raw_text: str  # All OCR'd text
    screenshot_path: Optional[str] = None
    analysis: Optional[str] = None


class VisionEngine:
    """
    Local vision processing engine.
    No cloud APIs. All models run locally.
    """

    def __init__(self, config_path: str = "config/settings.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.vision_config = self.config['vision']
        self.enabled = self.vision_config['enabled']

        # Initialize models
        self.detection_model = None
        self._init_object_detection()

        # Screen monitoring
        self.monitoring = False
        self.last_screen_state = None

        # Camera
        self.camera = None
        self.camera_id = self.vision_config.get('camera_id', 0)
        
        # Dynamic model resolution for Ollama LLaVA
        self._resolve_vision_model()

    def _resolve_vision_model(self):
        """Map generic 'llava' vision model to the exact tagged version in Ollama."""
        if not OLLAMA_AVAILABLE:
            return
        
        try:
            primary = self.config['models'].get('vision_model', 'llava')
            models_response = ollama.list()
            available = [m.get('name', m.get('model')) for m in models_response.get('models', [])]
            
            # Exact match
            if primary in available:
                self.config['models']['vision_model'] = primary
                return
                
            # Prefix match
            for m in available:
                if m.startswith(primary):
                    self.config['models']['vision_model'] = m
                    print(f"[Vision] Resolved vision model: {primary} -> {m}")
                    return
        except Exception as e:
            print(f"[Vision] Could not resolve vision model dynamically: {e}")

    def _init_object_detection(self):
        """Load YOLOv8 model for object detection."""
        if not YOLO_AVAILABLE or not self.vision_config.get('object_detection', False):
            return

        model_path = self.vision_config.get('detection_model', 'yolov8n.pt')

        # Download if not exists
        if not os.path.exists(model_path):
            print(f"[Vision] Downloading {model_path}...")
            # YOLO auto-downloads on first use

        try:
            self.detection_model = YOLO(model_path)
            print(f"[Vision] Object detection loaded: {model_path}")
        except Exception as e:
            print(f"[Vision] Failed to load detection model: {e}")

    # ==================== SCREEN CAPTURE ====================

    def capture_screen(self, region: Tuple[int, int, int, int] = None) -> Image.Image:
        """
        Capture full screen or specific region.
        region: (left, top, right, bottom)
        """
        if region:
            screenshot = ImageGrab.grab(bbox=region)
        else:
            screenshot = ImageGrab.grab()
        return screenshot

    def capture_active_window(self) -> Tuple[Image.Image, str]:
        """
        Capture only the currently focused window.
        Returns (image, window_title).
        """
        # Cross-platform window detection
        import platform

        if platform.system() == "Windows":
            try:
                import win32gui
                import win32ui
                import win32con

                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)

                # Get window dimensions
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                width = right - left
                height = bottom - top

                # Capture
                hwndDC = win32gui.GetWindowDC(hwnd)
                mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                saveDC = mfcDC.CreateCompatibleDC()

                saveBitMap = win32ui.CreateBitmap()
                saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
                saveDC.SelectObject(saveBitMap)
                saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)

                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)
                img = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1
                )

                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)

                return img, title
            except Exception as e:
                print(f"[Vision] Windows window capture failed: {e}")

        elif platform.system() == "Linux":
            try:
                import subprocess
                # Use xdotool to get active window ID
                result = subprocess.run(
                    ['xdotool', 'getactivewindow'],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    window_id = result.stdout.strip()
                    title_result = subprocess.run(
                        ['xdotool', 'getwindowname', window_id],
                        capture_output=True, text=True
                    )
                    title = title_result.stdout.strip()

                    # Capture using import (ImageMagick) or gnome-screenshot
                    temp_file = tempfile.mktemp(suffix='.png')
                    subprocess.run([
                        'gnome-screenshot', '-w', '-f', temp_file
                    ], check=True)
                    img = Image.open(temp_file)
                    os.remove(temp_file)
                    return img, title
            except Exception as e:
                print(f"[Vision] Linux window capture failed: {e}")

        # Fallback to full screen
        return self.capture_screen(), "Unknown"

    # ==================== OCR ====================

    def extract_text(self, image: Image.Image, preprocess: bool = True) -> str:
        """
        Extract all text from an image using Tesseract OCR.
        """
        if not TESSERACT_AVAILABLE:
            return "[OCR not available - install pytesseract and tesseract-ocr]"

        # Set absolute path for Windows if not in PATH
        if os.name == 'nt' and not shutil.which('tesseract'):
            tess_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            if os.path.exists(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path

        if preprocess:
            # Convert to OpenCV format and preprocess
            cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            # Denoise and threshold
            denoised = cv2.fastNlMeansDenoising(gray)
            _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            image = Image.fromarray(thresh)

        try:
            text = pytesseract.image_to_string(image)
            return text.strip()
        except Exception as e:
            return f"[OCR Error: {e}]"

    def extract_text_regions(self, image: Image.Image) -> List[Dict]:
        """
        Extract text with bounding boxes for UI interaction.
        Returns list of {text, bbox, confidence}
        """
        if not TESSERACT_AVAILABLE:
            return []

        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        data = pytesseract.image_to_data(cv_image, output_type=pytesseract.Output.DICT)

        regions = []
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            if int(data['conf'][i]) > 30:  # Confidence threshold
                text = data['text'][i].strip()
                if text:
                    x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                    regions.append({
                        'text': text,
                        'bbox': (x, y, x + w, y + h),
                        'confidence': data['conf'][i] / 100.0
                    })
        return regions

    def find_text_on_screen(self, target_text: str) -> Optional[Tuple[int, int]]:
        """
        Find specific text on screen and return center coordinates.
        Useful for "click the OK button" commands.
        """
        screenshot = self.capture_screen()
        regions = self.extract_text_regions(screenshot)

        for region in regions:
            if target_text.lower() in region['text'].lower():
                x1, y1, x2, y2 = region['bbox']
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                return (center_x, center_y)

        return None

    # ==================== OBJECT DETECTION ====================

    def detect_objects(self, image: Image.Image, confidence: float = 0.5) -> List[DetectedObject]:
        """
        Detect objects in image using local YOLOv8.
        """
        if self.detection_model is None:
            return []

        results = self.detection_model(image, verbose=False)
        detected = []

        for result in results:
            boxes = result.boxes
            for box in boxes:
                conf = float(box.conf[0])
                if conf >= confidence:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cls = int(box.cls[0])
                    label = result.names[cls]
                    center_x = (x1 + x2) // 2
                    center_y = (y1 + y2) // 2

                    detected.append(DetectedObject(
                        label=label,
                        confidence=conf,
                        bbox=(x1, y1, x2, y2),
                        center=(center_x, center_y)
                    ))

        return detected

    def find_object_on_screen(self, object_name: str) -> Optional[Tuple[int, int]]:
        """
        Find an object (e.g., "laptop", "phone", "cup") on screen.
        Returns center coordinates.
        """
        screenshot = self.capture_screen()
        objects = self.detect_objects(screenshot)

        for obj in objects:
            if object_name.lower() in obj.label.lower():
                return obj.center

        return None

    # ==================== UI ELEMENT DETECTION ====================

    def detect_ui_elements(self, image: Image.Image) -> List[UIElement]:
        """
        Detect interactive UI elements: buttons, input fields, checkboxes, etc.
        Combines OCR with contour detection.
        """
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        # Find contours that might be UI elements
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        elements = []
        text_regions = self.extract_text_regions(image)

        # Match text regions to contours to identify buttons/labels
        for region in text_regions:
            x1, y1, x2, y2 = region['bbox']
            # Check if there's a rectangular contour around this text
            for cnt in contours:
                cx, cy, cw, ch = cv2.boundingRect(cnt)
                # If contour surrounds or is near text
                if (cx - 5 <= x1 and cy - 5 <= y1 and 
                    cx + cw + 5 >= x2 and cy + ch + 5 >= y2):
                    elements.append(UIElement(
                        element_type="button" if cw < 300 and ch < 100 else "text_field",
                        text=region['text'],
                        bbox=(cx, cy, cx + cw, cy + ch),
                        confidence=region['confidence']
                    ))
                    break

        return elements

    def find_ui_element(self, element_description: str) -> Optional[Tuple[int, int]]:
        """
        Find a UI element by description.
        e.g., "OK button", "search box", "settings icon"
        """
        screenshot = self.capture_screen()
        elements = self.detect_ui_elements(screenshot)

        # Try exact match first
        for elem in elements:
            if element_description.lower() in elem.text.lower():
                x1, y1, x2, y2 = elem.bbox
                return ((x1 + x2) // 2, (y1 + y2) // 2)

        # Try partial match
        for elem in elements:
            words = element_description.lower().split()
            if any(word in elem.text.lower() for word in words):
                x1, y1, x2, y2 = elem.bbox
                return ((x1 + x2) // 2, (y1 + y2) // 2)

        return None

    # ==================== IMAGE UNDERSTANDING (LLaVA) ====================

    def analyze_image(self, image: Image.Image, prompt: str = "Describe what you see in detail.") -> str:
        """
        Analyze an image using local vision-language model (LLaVA via Ollama).
        Fully offline. No API calls.
        """
        if not OLLAMA_AVAILABLE:
            return "[Vision analysis unavailable - Ollama not installed]"

        # Save image temporarily
        temp_path = tempfile.mktemp(suffix='.png')
        image.save(temp_path)

        try:
            response = ollama.chat(
                model=self.config['models']['vision_model'],
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [temp_path]
                }]
            )
            os.remove(temp_path)
            return response['message']['content']
        except Exception as e:
            os.remove(temp_path)
            return f"[Vision analysis error: {e}]"

    def analyze_screen(self, prompt: str = "Describe the current screen state.") -> str:
        """Capture and analyze the current screen."""
        screenshot = self.capture_screen()
        return self.analyze_image(screenshot, prompt)

    def analyze_active_window(self) -> Dict[str, Any]:
        """Comprehensive analysis of active window."""
        screenshot, title = self.capture_active_window()

        # Parallel analysis
        text = self.extract_text(screenshot)
        objects = self.detect_objects(screenshot)
        ui_elements = self.detect_ui_elements(screenshot)

        # AI description
        description = self.analyze_image(screenshot, 
            "Describe this application window. What is the user doing? What UI elements are visible?")

        state = ScreenState(
            timestamp=__import__('datetime').datetime.now().isoformat(),
            active_window=title,
            detected_objects=objects,
            ui_elements=ui_elements,
            raw_text=text,
            analysis=description
        )

        self.last_screen_state = state
        return {
            'window': title,
            'description': description,
            'text_content': text[:1000],  # Truncate
            'objects': [{'label': o.label, 'confidence': o.confidence} for o in objects],
            'ui_elements_count': len(ui_elements),
            'interactive_elements': [
                {'type': e.element_type, 'text': e.text} 
                for e in ui_elements[:10]
            ]
        }

    # ==================== CAMERA ====================

    def init_camera(self) -> bool:
        """Initialize camera for visual input."""
        if not self.vision_config.get('camera_enabled', False):
            return False

        self.camera = cv2.VideoCapture(self.camera_id)
        if not self.camera.isOpened():
            print("[Vision] Could not open camera")
            return False
        return True

    def capture_camera_frame(self) -> Optional[Image.Image]:
        """Capture a single frame from camera."""
        if self.camera is None:
            if not self.init_camera():
                return None

        ret, frame = self.camera.read()
        if ret:
            return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        return None

    def analyze_camera_feed(self, prompt: str = "What do you see?") -> str:
        """Capture from camera and analyze."""
        frame = self.capture_camera_frame()
        if frame is None:
            return "[Camera not available]"
        return self.analyze_image(frame, prompt)

    def release_camera(self):
        """Release camera resources."""
        if self.camera:
            self.camera.release()
            self.camera = None

    # ==================== SCREEN MONITORING ====================

    def start_monitoring(self, callback=None, interval: int = 5):
        """
        Start continuous screen monitoring.
        Calls callback with ScreenState whenever significant change detected.
        """
        import threading
        import time

        self.monitoring = True

        def monitor_loop():
            last_hash = None
            while self.monitoring:
                screenshot = self.capture_screen()
                # Simple hash for change detection
                current_hash = hash(screenshot.tobytes())

                if current_hash != last_hash:
                    last_hash = current_hash
                    state = self.analyze_active_window()
                    if callback:
                        callback(state)

                time.sleep(interval)

        threading.Thread(target=monitor_loop, daemon=True).start()

    def stop_monitoring(self):
        self.monitoring = False

    # ==================== UTILITY ====================

    def annotate_image(self, image: Image.Image, detections: List[DetectedObject]) -> Image.Image:
        """Draw bounding boxes and labels on image."""
        draw = ImageDraw.Draw(image)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
        except:
            font = ImageFont.load_default()

        for det in detections:
            x1, y1, x2, y2 = det.bbox
            draw.rectangle([x1, y1, x2, y2], outline="red", width=2)
            label = f"{det.label} {det.confidence:.2f}"
            draw.text((x1, y1 - 20), label, fill="red", font=font)

        return image


