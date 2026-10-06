
"""
Intent Classifier for VICTOR
- Uses Hugging Face Transformers for NLP
- Classifies user intents
- Maps to skills and actions
"""
import re

try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class IntentClassifier:
    """
    Intent classification system.
    Uses rule-based and optional transformers for classification.
    """

    def __init__(self):
        self.intent_patterns = {
            'system_control': [
                'launch', 'open', 'start', 'close', 'shutdown', 'restart',
                'time', 'date', 'what time', 'system info', 'computer info'
            ],
            'file_manager': [
                'read file', 'list directory', 'search files', 'file info',
                'open file', 'what\'s in', 'folder contents'
            ],
            'terminal': [
                'run command', 'execute', 'cmd', 'powershell', 'shell',
                'list directory', 'cd', 'change directory'
            ],
            'penetration_testing': [
                'port scan', 'scan ports', 'nmap', 'network scan',
                'whois', 'dns lookup', 'subdomain', 'http headers'
            ],
            'screen_automation': [
                'screenshot', 'capture screen', 'take screenshot',
                'analyze screen', 'what\'s on screen', 'look at screen',
                'move mouse', 'click', 'type text'
            ],
            'cooking': [
                'recipe', 'cook', 'bake', 'ingredient', 'measurement',
                'convert', 'kitchen timer', 'cooking tip'
            ],
            'vision': [
                'camera', 'take photo', 'capture image', 'what do you see',
                'detect objects', 'identify'
            ],
            'browser': [
                'browse', 'search web', 'open website', 'google', 'search for'
            ],
            'code_executor': [
                'run code', 'execute code', 'python', 'javascript', 'compile'
            ]
        }

        self.classifier = None
        # Disable transformers by default for faster startup
        # if TRANSFORMERS_AVAILABLE:
        #     try:
        #         self.classifier = pipeline(
        #             "text-classification",
        #             model="distilbert-base-uncased-finetuned-sst-2-english"
        #         )
        #         print("[Intent Classifier] Transformers loaded")
        #     except Exception as e:
        #         print(f"[Intent Classifier] Could not load transformers: {e}")
        print("[Intent Classifier] Rule-based classification only (fast mode)")

    def classify_intent(self, query):
        """
        Classify user intent.
        Returns (intent_name, confidence).
        """
        query_lower = query.lower()

        # Rule-based classification first (fast, reliable)
        best_intent = 'general'
        best_confidence = 0.5

        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    confidence = 0.8 + (0.05 * len(pattern.split()))
                    if confidence > best_confidence:
                        best_confidence = min(confidence, 0.98)
                        best_intent = intent

        # Fallback to transformers if available
        if TRANSFORMERS_AVAILABLE and self.classifier and best_confidence < 0.7:
            try:
                result = self.classifier(query)
                if result:
                    label = result[0]['label']
                    score = result[0]['score']
                    if score > 0.8:
                        best_confidence = max(best_confidence, score * 0.8)
            except Exception as e:
                pass

        return best_intent, best_confidence

    def extract_entities(self, query):
        """
        Extract entities from query (simple rule-based).
        """
        entities = {}

        # Extract file paths
        path_match = re.search(r'([~./\\][^\s]+)', query)
        if path_match:
            entities['path'] = path_match.group(1)

        # Extract URLs
        url_match = re.search(r'(https?://[^\s]+)', query)
        if url_match:
            entities['url'] = url_match.group(1)

        # Extract numbers
        numbers = re.findall(r'\d+', query)
        if numbers:
            entities['numbers'] = numbers

        return entities

