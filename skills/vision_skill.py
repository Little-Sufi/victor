from .base_skill import BaseSkill

class VisionSkill(BaseSkill):
    @property
    def skill_id(self):
        return "vision"
    
    @property
    def description(self):
        return "Vision capabilities: camera, object detection, screen capture"
    
    @property
    def version(self):
        return "1.0.0"
    
    def can_handle(self, query: str):
        query_lower = query.lower()
        vision_keywords = ["what do you see", "camera", "look at", "take picture", "screenshot", "detect", "screen capture"]
        if any(k in query_lower for k in vision_keywords):
            return 1.0
        return 0.0
    
    def handle(self, query: str, params=None):
        try:
            if not hasattr(self, 'victor') or not hasattr(self.victor, 'vision'):
                return "Vision system not available"
            
            query_lower = query.lower()
            
            if "screenshot" in query_lower or "screen capture" in query_lower:
                img = self.victor.vision.capture_screen()
                return "Screenshot captured!"
            
            if any(k in query_lower for k in ["what do you see", "look at", "camera", "take picture"]):
                if hasattr(self.victor.vision, 'detection_model') and self.victor.vision.detection_model:
                    img = self.victor.vision.capture_screen()
                    results = self.victor.vision.detection_model(img)
                    objects = []
                    for r in results:
                        for box in r.boxes:
                            label = r.names[int(box.cls[0])]
                            conf = float(box.conf[0])
                            objects.append(f"{label} ({conf:.2f})")
                    if objects:
                        return f"I see: {', '.join(objects[:10])}"
                    else:
                        return "No objects detected"
                else:
                    return "Vision detection model not loaded"
            
            return "Vision capability available"
        except Exception as e:
            return f"Vision error: {str(e)}"
