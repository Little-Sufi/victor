/**
 * VICTOR Gesture Recognition & Camera Vision Engine
 * Powered by MediaPipe Hands & Web Camera API
 * Provides real-time hand tracking, skeleton visualization, and gesture classification.
 */

export class VictorGestureController {
  constructor(options = {}) {
    this.videoElement = options.videoElement;
    this.canvasElement = options.canvasElement;
    this.onGesture = options.onGesture || (() => {});
    this.onStatus = options.onStatus || (() => {});
    
    this.hands = null;
    this.camera = null;
    this.isActive = false;
    this.ws = null;
    this.lastGesture = null;
    this.lastGestureTime = 0;
    this.gestureCooldownMs = 1200; // Prevent spamming duplicate events
    
    this._connectWebSocket();
  }

  _connectWebSocket() {
    try {
      this.ws = new WebSocket('ws://127.0.0.1:8765');
      this.ws.onopen = () => {
        console.log('[VICTOR Gestures] Connected to Node IPC WebSocket.');
      };
      this.ws.onerror = () => {
        // Silent fallback if Node service is not running
      };
      this.ws.onclose = () => {
        // Auto-reconnect after 3s
        setTimeout(() => this._connectWebSocket(), 3000);
      };
    } catch (e) {
      // Ignore
    }
  }

  async start() {
    if (this.isActive) return;
    this.onStatus('Initializing Camera & Vision AI...');

    try {
      // Load MediaPipe Hands
      if (typeof window.Hands === 'undefined') {
        await this._loadScript('./node_modules/@mediapipe/hands/hands.js');
      }
      if (typeof window.Camera === 'undefined') {
        await this._loadScript('./node_modules/@mediapipe/camera_utils/camera_utils.js');
      }

      this.hands = new window.Hands({
        locateFile: (file) => `./node_modules/@mediapipe/hands/${file}`
      });

      this.hands.setOptions({
        maxNumHands: 1,
        modelComplexity: 1,
        minDetectionConfidence: 0.65,
        minTrackingConfidence: 0.65
      });

      this.hands.onResults((results) => this._onResults(results));

      this.camera = new window.Camera(this.videoElement, {
        onFrame: async () => {
          if (this.isActive) {
            await this.hands.send({ image: this.videoElement });
          }
        },
        width: 640,
        height: 480
      });

      await this.camera.start();
      this.isActive = true;
      this.onStatus('Camera & Gesture Tracking ACTIVE');
      console.log('[VICTOR Gestures] Vision system online.');
    } catch (err) {
      console.error('[VICTOR Gestures] Failed to start gesture system:', err);
      this.onStatus('Camera access error: ' + err.message);
    }
  }

  stop() {
    if (!this.isActive) return;
    this.isActive = false;
    if (this.camera && typeof this.camera.stop === 'function') {
      try { this.camera.stop(); } catch (e) {}
    }
    if (this.canvasElement) {
      const ctx = this.canvasElement.getContext('2d');
      ctx.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height);
    }
    this.onStatus('Camera Standby');
  }

  _loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = reject;
      document.head.appendChild(s);
    });
  }

  _onResults(results) {
    if (!this.isActive || !this.canvasElement) return;

    const canvas = this.canvasElement;
    const ctx = canvas.getContext('2d');
    canvas.width = this.videoElement.videoWidth || 640;
    canvas.height = this.videoElement.videoHeight || 480;

    ctx.save();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
      const landmarks = results.multiHandLandmarks[0];
      
      // Draw Holographic Skeleton
      this._drawSkeleton(ctx, landmarks, canvas.width, canvas.height);

      // Classify Gesture
      const gesture = this._classifyGesture(landmarks);
      if (gesture) {
        this._dispatchGesture(gesture);
      }
    }

    ctx.restore();
  }

  _drawSkeleton(ctx, lm, w, h) {
    const connections = [
      [0,1],[1,2],[2,3],[3,4],        // Thumb
      [0,5],[5,6],[6,7],[7,8],        // Index
      [0,9],[9,10],[10,11],[11,12],   // Middle
      [0,13],[13,14],[14,15],[15,16], // Ring
      [0,17],[17,18],[18,19],[19,20], // Pinky
      [5,9],[9,13],[13,17]            // Palm
    ];

    // Neon Cyan glow lines
    ctx.lineWidth = 3;
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.75)';
    ctx.shadowColor = '#00f0ff';
    ctx.shadowBlur = 10;

    for (const [i, j] of connections) {
      ctx.beginPath();
      ctx.moveTo(lm[i].x * w, lm[i].y * h);
      ctx.lineTo(lm[j].x * w, lm[j].y * h);
      ctx.stroke();
    }

    // Glowing joints
    ctx.fillStyle = '#ffffff';
    for (const pt of lm) {
      ctx.beginPath();
      ctx.arc(pt.x * w, pt.y * h, 4, 0, 2 * Math.PI);
      ctx.fill();
    }
  }

  _classifyGesture(lm) {
    // 0: Wrist, 4: Thumb, 8: Index, 12: Middle, 16: Ring, 20: Pinky
    // Fingers extended check: tip.y < pip.y (lower Y is higher up in screen space)
    const isIndexExtended = lm[8].y < lm[6].y;
    const isMiddleExtended = lm[12].y < lm[10].y;
    const isRingExtended = lm[16].y < lm[14].y;
    const isPinkyExtended = lm[20].y < lm[18].y;
    const isThumbExtended = lm[4].y < lm[2].y;

    // Distance between thumb tip and index tip
    const pinchDist = Math.hypot(lm[4].x - lm[8].x, lm[4].y - lm[8].y);

    // 1. PINCH (Thumb tip touches Index tip)
    if (pinchDist < 0.06) {
      return { name: 'pinch', label: '🤏 Pinch (Click)', confidence: 0.95 };
    }

    // 2. OPEN PALM / WAVE (All 5 extended)
    if (isThumbExtended && isIndexExtended && isMiddleExtended && isRingExtended && isPinkyExtended) {
      return { name: 'open_palm', label: '🖐️ Open Hand (Wake / Listen)', confidence: 0.92 };
    }

    // 3. FIST (All 4 curled)
    if (!isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
      if (isThumbExtended) {
        // 4. THUMBS UP
        return { name: 'thumbs_up', label: '👍 Thumbs Up (Acknowledge)', confidence: 0.94 };
      }
      return { name: 'fist', label: '✊ Closed Fist (Mute / Stop)', confidence: 0.90 };
    }

    // 5. PEACE / VICTORY (Index and Middle extended, Ring and Pinky curled)
    if (isIndexExtended && isMiddleExtended && !isRingExtended && !isPinkyExtended) {
      return { name: 'victory', label: '✌️ Victory (Screenshot)', confidence: 0.92 };
    }

    // 6. POINTING (Index only extended)
    if (isIndexExtended && !isMiddleExtended && !isRingExtended && !isPinkyExtended) {
      return { 
        name: 'point', 
        label: '☝️ Pointing (Navigate)', 
        x: lm[8].x, 
        y: lm[8].y, 
        confidence: 0.88 
      };
    }

    return null;
  }

  _dispatchGesture(gesture) {
    const now = Date.now();
    if (this.lastGesture === gesture.name && (now - this.lastGestureTime) < this.gestureCooldownMs) {
      return;
    }

    this.lastGesture = gesture.name;
    this.lastGestureTime = now;

    // Trigger local UI callback
    this.onGesture(gesture);

    // Forward to WebSocket if connected
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'gesture',
        gesture: gesture.name,
        label: gesture.label,
        x: gesture.x || null,
        y: gesture.y || null,
        confidence: gesture.confidence,
        timestamp: now
      }));
    }
  }
}
