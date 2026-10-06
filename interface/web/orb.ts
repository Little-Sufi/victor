import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { ShaderPass } from "three/addons/postprocessing/ShaderPass.js";

export type OrbStatus = "idle" | "listening" | "processing" | "speaking";

export interface OrbSceneApi {
  rotateBy(deltaTheta: number, deltaPhi: number): void;
  zoomBy(factor: number): void;
  zoomIn(): void;
  zoomOut(): void;
  resetView(): void;
  setStatus(status: OrbStatus): void;
  setDynamics(rotationSpeed: number, pulseHz: number, isAudioActive: boolean): void;
  resize(width: number, height: number): void;
  getCameraDistance(): number;
  dispose(): void;
  updateColors(primaryHex: number, secondaryHex: number): void;
}

const HOME_POSITION = new THREE.Vector3(0, 0, 4.2);
const MIN_DISTANCE = 0.5;
const MAX_DISTANCE = 35;

const FresnelBubbleShader = {
  vertexShader: `
    varying vec3 vNormal;
    varying vec3 vViewPosition;
    void main() {
      vNormal = normalize(normalMatrix * normal);
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      vViewPosition = -mvPosition.xyz;
      gl_Position = projectionMatrix * mvPosition;
    }
  `,
  fragmentShader: `
    uniform vec3 uColor;
    uniform vec3 uRimColor;
    uniform float uTime;
    varying vec3 vNormal;
    varying vec3 vViewPosition;
    void main() {
      vec3 normal = normalize(vNormal);
      vec3 viewDir = normalize(vViewPosition);
      float fresnel = pow(1.0 - clamp(abs(dot(viewDir, normal)), 0.0, 1.0), 3.0);
      float shimmer = sin(uTime * 2.8 + normal.y * 6.0 + normal.x * 4.0) * 0.15 + 0.85;
      vec3 rimCol = mix(uRimColor, uColor, 0.35) * shimmer;
      vec3 lightDir = normalize(vec3(0.6, 0.8, 1.0));
      vec3 halfDir = normalize(lightDir + viewDir);
      float spec = pow(max(dot(normal, halfDir), 0.0), 48.0) * 0.6;
      float alpha = clamp(fresnel * 0.85 + spec * 0.7, 0.0, 0.95);
      vec3 finalCol = (rimCol * fresnel) + vec3(spec * 0.9);
      gl_FragColor = vec4(finalCol, alpha);
    }
  `
};

const ProceduralMultiverseDotShader = {
  vertexShader: `
    varying vec2 vUv;
    varying vec3 vWorldPosition;
    varying vec3 vNormal;
    void main() {
      vUv = uv;
      vNormal = normalize(normalMatrix * normal);
      vec4 worldPosition = modelMatrix * vec4(position, 1.0);
      vWorldPosition = worldPosition.xyz;
      gl_Position = projectionMatrix * viewMatrix * worldPosition;
    }
  `,
  fragmentShader: `
    uniform float uTime;
    uniform vec3 uPrimaryColor;
    uniform vec3 uSecondaryColor;
    uniform float uAudio;
    varying vec2 vUv;
    varying vec3 vWorldPosition;
    varying vec3 vNormal;
    float hash3D(vec3 p) {
      p = fract(p * vec3(443.897, 441.423, 437.195));
      p += dot(p, p.yzx + 19.19);
      return fract((p.x + p.y) * p.z);
    }
    vec2 voronoi3D(vec3 x) {
      vec3 n = floor(x);
      vec3 f = fract(x);
      float md = 8.0;
      float id = 0.0;
      for (int k = -1; k <= 1; k++) {
        for (int j = -1; j <= 1; j++) {
          for (int i = -1; i <= 1; i++) {
            vec3 g = vec3(float(i), float(j), float(k));
            vec3 o = vec3(
              hash3D(n + g),
              hash3D(n + g + vec3(11.0, 37.0, 71.0)),
              hash3D(n + g + vec3(53.0, 97.0, 13.0))
            );
            o = 0.5 + 0.45 * sin(uTime * 1.2 + 6.2831 * o);
            vec3 r = g + o - f;
            float d = dot(r, r);
            if (d < md) {
              md = d;
              id = hash3D(n + g + vec3(101.0, 103.0, 107.0));
            }
          }
        }
      }
      return vec2(sqrt(md), id);
    }
    void main() {
      vec3 pos = vWorldPosition * 3.5;
      float angle = uTime * 0.12;
      mat2 rot = mat2(cos(angle), -sin(angle), sin(angle), cos(angle));
      pos.xz = rot * pos.xz;
      vec2 voro1 = voronoi3D(pos * 3.2 + vec3(0.0, uTime * 0.1, 0.0));
      float dotMask1 = smoothstep(0.16, 0.02, voro1.x);
      vec2 voro2 = voronoi3D(pos * 1.6 - vec3(uTime * 0.08, 0.0, uTime * 0.05));
      float dotMask2 = smoothstep(0.20, 0.03, voro2.x);
      float spark = pow(sin(uTime * 3.5 + voro1.y * 30.0) * 0.5 + 0.5, 5.0) * (1.0 + uAudio * 1.5);
      vec3 color1 = mix(uPrimaryColor, vec3(0.0, 0.95, 1.0), voro1.y);
      vec3 color2 = mix(uSecondaryColor, vec3(1.0, 1.0, 1.0), voro2.y);
      vec3 finalColor = (color1 * dotMask1 * 1.5) + (color2 * dotMask2 * 1.0) + (vec3(1.0) * spark * dotMask1);
      float fresnel = pow(1.0 - clamp(abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 0.0, 1.0), 2.0);
      float alpha = clamp((dotMask1 * 0.85 + dotMask2 * 0.5 + spark * 0.6) * (0.65 + 0.35 * fresnel), 0.0, 0.95);
      gl_FragColor = vec4(finalColor, alpha);
    }
  `
};

const MultiverseStarShader = {
  vertexShader: `
    attribute float aSize;
    attribute float aPhase;
    attribute float aSpeed;
    attribute vec3 aColor;
    attribute float aIsFlare;
    varying float vPhase;
    varying float vSpeed;
    varying vec3 vColor;
    varying float vIsFlare;
    uniform float uTime;
    uniform float uAudio;
    void main() {
      vPhase = aPhase;
      vSpeed = aSpeed;
      vColor = aColor;
      vIsFlare = aIsFlare;
      vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
      float pulse = sin(uTime * aSpeed * 4.0 + aPhase * 17.3) * 0.5 + 0.5;
      float dynamicSize = aSize * (0.65 + 0.7 * pulse) * (1.0 + uAudio * 0.45);
      gl_PointSize = dynamicSize * (180.0 / -mvPosition.z);
      gl_Position = projectionMatrix * mvPosition;
    }
  `,
  fragmentShader: `
    uniform float uTime;
    varying float vPhase;
    varying float vSpeed;
    varying vec3 vColor;
    varying float vIsFlare;
    void main() {
      vec2 coord = gl_PointCoord - vec2(0.5);
      float dist = length(coord);
      if (dist > 0.5) discard;
      float alphaMask = smoothstep(0.5, 0.02, dist);
      float blinkRaw = sin(uTime * vSpeed * 14.0 + vPhase * 31.7) * 0.5 + 0.5;
      float blink = pow(blinkRaw, 3.5);
      float spark = step(0.72, blinkRaw) * 0.7;
      vec3 finalColor = mix(vColor, vec3(1.0, 1.0, 1.0), spark * 0.8);
      if (vIsFlare > 0.5) {
        float absX = abs(coord.x);
        float absY = abs(coord.y);
        float crossRay = max(
          smoothstep(0.22, 0.0, absX) * smoothstep(0.5, 0.0, absY),
          smoothstep(0.22, 0.0, absY) * smoothstep(0.5, 0.0, absX)
        );
        float coreGlow = smoothstep(0.3, 0.0, dist);
        alphaMask = max(coreGlow, crossRay * 0.9);
      }
      float finalAlpha = alphaMask * (0.2 + 0.8 * (blink + spark));
      gl_FragColor = vec4(finalColor, finalAlpha);
    }
  `
};

export function createOrbScene(container: HTMLElement, initialColorHex: number = 0x00f0ff): OrbSceneApi {
  const width = container.clientWidth || window.innerWidth;
  const height = container.clientHeight || window.innerHeight;
  const isMini = width <= 120 || height <= 120;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
  camera.position.copy(isMini ? new THREE.Vector3(0, 0, 4.8) : HOME_POSITION);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setClearColor(0x000000, 0);
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);

  const renderTarget = new THREE.WebGLRenderTarget(width, height, {
    type: THREE.HalfFloatType,
    format: THREE.RGBAFormat,
    colorSpace: THREE.SRGBColorSpace,
  });
  const composer = new EffectComposer(renderer, renderTarget);
  composer.addPass(new RenderPass(scene, camera));
  const bloomStrengthVal = isMini ? 0.35 : 0.65;
  const bloom = new UnrealBloomPass(new THREE.Vector2(width, height), bloomStrengthVal, 0.4, 0.2);
  composer.addPass(bloom);

  const chromaticShader = {
    uniforms: {
      tDiffuse: { value: null },
      uTime: { value: 0 },
      uIntensity: { value: isMini ? 0.0006 : 0.002 },
    },
    vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: `
      uniform sampler2D tDiffuse; uniform float uIntensity; varying vec2 vUv;
      void main() {
        vec2 dir = vUv - vec2(0.5); float d = length(dir); float offset = uIntensity * d;
        vec4 cr = texture2D(tDiffuse, vUv + dir * offset);
        vec4 cg = texture2D(tDiffuse, vUv);
        vec4 cb = texture2D(tDiffuse, vUv - dir * offset * 0.5);
        gl_FragColor = vec4(cr.r * 0.92, cg.g * 1.08, cb.b * 1.12, 1.0);
      }
    `,
  };
  const chromaticPass = new ShaderPass(chromaticShader);
  composer.addPass(chromaticPass);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.04;
  controls.minDistance = MIN_DISTANCE;
  controls.maxDistance = MAX_DISTANCE;
  controls.zoomSpeed = 1.4;
  controls.enablePan = false;

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.9);
  scene.add(ambientLight);

  const pointLight = new THREE.PointLight(initialColorHex, 2.5, 50);
  pointLight.position.set(0, 0, 0);
  scene.add(pointLight);

  const skyBlue = new THREE.Color(0x38bdf8);
  const electricCyan = new THREE.Color(0x00f0ff);
  const iceBlue = new THREE.Color(0x7dd3fc);
  const pureWhite = new THREE.Color(0xffffff);
  const cosmicPurple = new THREE.Color(0xc084fc);
  const starGold = new THREE.Color(0xfde047);
  const deepBlue = new THREE.Color(0x0284c7);
  const colorPalette = [skyBlue, electricCyan, iceBlue, pureWhite, cosmicPurple, starGold, deepBlue];

  let currentStatus: OrbStatus = "idle";
  let primaryColorHex = initialColorHex;
  let secondaryColorHex = 0x8b5cf6;
  let rotationSpeed = 0.006;
  let pulseHz = 2.0;
  let isAudioActive = false;

  const sphereGeo = new THREE.SphereGeometry(0.92, 64, 64);
  const coreMaterial = new THREE.MeshBasicMaterial({ color: 0x020617, transparent: true, opacity: 0.65 });
  const coreMesh = new THREE.Mesh(sphereGeo, coreMaterial);
  scene.add(coreMesh);

  const fresnelShaderMaterial = new THREE.ShaderMaterial({
    vertexShader: FresnelBubbleShader.vertexShader,
    fragmentShader: FresnelBubbleShader.fragmentShader,
    uniforms: {
      uColor: { value: new THREE.Color(primaryColorHex) },
      uRimColor: { value: new THREE.Color(0x00f0ff) },
      uTime: { value: 0 },
    },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide,
  });
  const haloGeo = new THREE.SphereGeometry(0.96, 64, 64);
  const multiverseRimHalo = new THREE.Mesh(haloGeo, fresnelShaderMaterial);
  coreMesh.add(multiverseRimHalo);

  const proceduralDotShaderMaterial = new THREE.ShaderMaterial({
    vertexShader: ProceduralMultiverseDotShader.vertexShader,
    fragmentShader: ProceduralMultiverseDotShader.fragmentShader,
    uniforms: {
      uTime: { value: 0 },
      uPrimaryColor: { value: new THREE.Color(primaryColorHex) },
      uSecondaryColor: { value: new THREE.Color(secondaryColorHex) },
      uAudio: { value: 0 },
    },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.FrontSide,
  });
  const proceduralDotGeo = new THREE.SphereGeometry(0.94, 64, 64);
  const proceduralDotMesh = new THREE.Mesh(proceduralDotGeo, proceduralDotShaderMaterial);
  coreMesh.add(proceduralDotMesh);

  const multiverseShaderMaterial = new THREE.ShaderMaterial({
    vertexShader: MultiverseStarShader.vertexShader,
    fragmentShader: MultiverseStarShader.fragmentShader,
    uniforms: { uTime: { value: 0 }, uAudio: { value: 0 } },
    transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
  });

  function createMultiverseStarField(count: number, radiusMax: number, colors: THREE.Color[]): THREE.Points {
    const positions = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    const phases = new Float32Array(count);
    const speeds = new Float32Array(count);
    const pointColors = new Float32Array(count * 3);
    const isFlares = new Float32Array(count);
    const clusters = [
      new THREE.Vector3(0.25, 0.15, 0.20), new THREE.Vector3(-0.30, -0.20, 0.10),
      new THREE.Vector3(0.05, -0.35, -0.25), new THREE.Vector3(-0.20, 0.30, -0.15)
    ];

    for (let i = 0; i < count; i++) {
      const idx3 = i * 3;
      let pos = new THREE.Vector3();
      const randType = Math.random();
      if (randType < 0.55) {
        const u = Math.random(); const v = Math.random();
        const theta = u * 2.0 * Math.PI; const phi = Math.acos(2.0 * v - 1.0);
        const r = radiusMax * (0.94 + Math.random() * 0.06);
        pos.set(r * Math.sin(phi) * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta), r * Math.cos(phi));
      } else if (randType < 0.85) {
        const cluster = clusters[Math.floor(Math.random() * clusters.length)];
        const spread = 0.25;
        pos.set(cluster.x + (Math.random() - 0.5) * spread, cluster.y + (Math.random() - 0.5) * spread, cluster.z + (Math.random() - 0.5) * spread);
        if (pos.length() > radiusMax * 0.9) pos.normalize().multiplyScalar(radiusMax * (0.4 + Math.random() * 0.5));
      } else {
        const r = Math.pow(Math.random(), 0.6) * radiusMax * 0.88;
        const u = Math.random(); const v = Math.random();
        const theta = u * 2.0 * Math.PI; const phi = Math.acos(2.0 * v - 1.0);
        pos.set(r * Math.sin(phi) * Math.cos(theta), r * Math.sin(phi) * Math.sin(theta), r * Math.cos(phi));
      }
      positions[idx3] = pos.x; positions[idx3 + 1] = pos.y; positions[idx3 + 2] = pos.z;
      const isFlare = Math.random() < 0.015;
      isFlares[i] = isFlare ? 1.0 : 0.0;
      sizes[i] = isFlare ? (0.05 + Math.random() * 0.06) : (0.012 + Math.random() * 0.028);
      phases[i] = Math.random() * 100.0;
      speeds[i] = 1.5 + Math.random() * 18.0;
      const col = colors[Math.floor(Math.random() * colors.length)];
      pointColors[idx3] = col.r; pointColors[idx3 + 1] = col.g; pointColors[idx3 + 2] = col.b;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    geo.setAttribute("aPhase", new THREE.BufferAttribute(phases, 1));
    geo.setAttribute("aSpeed", new THREE.BufferAttribute(speeds, 1));
    geo.setAttribute("aColor", new THREE.BufferAttribute(pointColors, 3));
    geo.setAttribute("aIsFlare", new THREE.BufferAttribute(isFlares, 1));
    return new THREE.Points(geo, multiverseShaderMaterial);
  }

  const multiverseStarCloud = createMultiverseStarField(isMini ? 6000 : 22000, 0.93, colorPalette);
  coreMesh.add(multiverseStarCloud);

  const satelliteUniversesGroup = new THREE.Group();
  scene.add(satelliteUniversesGroup);
  const satelliteStarClouds: THREE.Points[] = [];
  const satelliteConfigs = [
    { pos: new THREE.Vector3(-1.45, 1.15, -0.6), scale: 0.38 },
    { pos: new THREE.Vector3(1.50, 0.95, -0.7), scale: 0.42 },
    { pos: new THREE.Vector3(-1.35, -0.95, -0.5), scale: 0.32 },
    { pos: new THREE.Vector3(1.40, -1.05, -0.6), scale: 0.36 },
    { pos: new THREE.Vector3(0.10, 1.55, -0.9), scale: 0.28 },
    { pos: new THREE.Vector3(-0.65, -1.50, -0.8), scale: 0.30 },
  ];

  satelliteConfigs.forEach((sat) => {
    const satGroup = new THREE.Group();
    satGroup.position.copy(sat.pos); satGroup.scale.set(sat.scale, sat.scale, sat.scale);
    const satSphereGeo = new THREE.SphereGeometry(0.92, 32, 32);
    const satBgMat = new THREE.MeshBasicMaterial({ color: 0x030712, transparent: true, opacity: 0.85 });
    satGroup.add(new THREE.Mesh(satSphereGeo, satBgMat));
    satGroup.add(new THREE.Mesh(new THREE.SphereGeometry(0.96, 32, 32), fresnelShaderMaterial));
    const satStarCloud = createMultiverseStarField(isMini ? 1200 : 4500, 0.92, colorPalette);
    satGroup.add(satStarCloud); satelliteStarClouds.push(satStarCloud);
    satelliteUniversesGroup.add(satGroup);
  });

  const innerGeo = new THREE.DodecahedronGeometry(1.15, 1);
  const innerLineMaterial = new THREE.LineBasicMaterial({ color: primaryColorHex, transparent: true, opacity: 0.22 });
  const innerWireframe = new THREE.LineSegments(new THREE.WireframeGeometry(innerGeo), innerLineMaterial);
  scene.add(innerWireframe);

  const outerGeo = new THREE.IcosahedronGeometry(1.45, 1);
  const outerLineMaterial = new THREE.LineBasicMaterial({ color: secondaryColorHex, transparent: true, opacity: 0.15 });
  const outerWireframe = new THREE.LineSegments(new THREE.WireframeGeometry(outerGeo), outerLineMaterial);
  scene.add(outerWireframe);

  const ringsGroup = new THREE.Group();
  [1.35, 1.65, 1.95].forEach((r, idx) => {
    const ringGeo = new THREE.RingGeometry(r, r + 0.015, 64);
    const ringMat = new THREE.MeshBasicMaterial({ color: idx % 2 === 0 ? primaryColorHex : secondaryColorHex, side: THREE.DoubleSide, transparent: true, opacity: 0.28 });
    const ringMesh = new THREE.Mesh(ringGeo, ringMat);
    ringMesh.rotation.x = Math.PI / 2 + idx * 0.3; ringMesh.rotation.y = idx * 0.4;
    ringsGroup.add(ringMesh);
  });
  scene.add(ringsGroup);

  const particleCount = isMini ? 150 : 450;
  const particleGeo = new THREE.BufferGeometry();
  const particlePos = new Float32Array(particleCount * 3);
  for (let p = 0; p < particleCount * 3; p += 3) {
    particlePos[p] = (Math.random() - 0.5) * 6; particlePos[p + 1] = (Math.random() - 0.5) * 6; particlePos[p + 2] = (Math.random() - 0.5) * 6;
  }
  particleGeo.setAttribute("position", new THREE.BufferAttribute(particlePos, 3));
  const particleMaterial = new THREE.PointsMaterial({ color: primaryColorHex, size: 0.025, transparent: true, opacity: 0.45 });
  const particles = new THREE.Points(particleGeo, particleMaterial);
  scene.add(particles);

  const dustCount = isMini ? 250 : 800;
  const dustGeo = new THREE.BufferGeometry();
  const dustPos = new Float32Array(dustCount * 3);
  for (let d = 0; d < dustCount * 3; d += 3) {
    dustPos[d] = (Math.random() - 0.5) * 12; dustPos[d + 1] = (Math.random() - 0.5) * 12; dustPos[d + 2] = (Math.random() - 0.5) * 12;
  }
  dustGeo.setAttribute("position", new THREE.BufferAttribute(dustPos, 3));
  const dustMaterial = new THREE.PointsMaterial({ color: 0x38bdf8, size: 0.018, transparent: true, opacity: 0.25 });
  const dustPoints = new THREE.Points(dustGeo, dustMaterial);
  scene.add(dustPoints);

  const clock = new THREE.Clock();
  let rafId = 0;
  let disposed = false;

  function animate() {
    if (disposed) return;
    rafId = requestAnimationFrame(animate);
    const time = clock.getElapsedTime();
    let speed = rotationSpeed;
    let pulse = pulseHz;
    let audioActive = isAudioActive;

    if (currentStatus === "speaking") { speed = Math.max(speed, 0.022); pulse = Math.max(pulse, 7.0); audioActive = true; }
    else if (currentStatus === "listening") { speed = Math.max(speed, 0.012); pulse = Math.max(pulse, 3.5); audioActive = true; }
    else if (currentStatus === "processing") { speed = Math.max(speed, 0.028); pulse = Math.max(pulse, 10.0); audioActive = true; }

    const audioMultiplier = audioActive ? 2.2 : 1.0;
    multiverseShaderMaterial.uniforms.uTime.value = time;
    multiverseShaderMaterial.uniforms.uAudio.value = audioActive ? 1.0 : 0.0;
    fresnelShaderMaterial.uniforms.uTime.value = time;
    proceduralDotShaderMaterial.uniforms.uTime.value = time;
    proceduralDotShaderMaterial.uniforms.uAudio.value = audioActive ? 1.0 : 0.0;

    coreMesh.rotation.y += speed * 0.4 * audioMultiplier;
    proceduralDotMesh.rotation.y += speed * 0.6 * audioMultiplier;
    proceduralDotMesh.rotation.x += speed * 0.2 * audioMultiplier;
    multiverseStarCloud.rotation.y += speed * 0.8 * audioMultiplier;
    multiverseStarCloud.rotation.x -= speed * 0.3 * audioMultiplier;

    satelliteUniversesGroup.rotation.y += speed * 0.25 * audioMultiplier;
    satelliteUniversesGroup.rotation.z += speed * 0.12 * audioMultiplier;
    satelliteStarClouds.forEach((cloud, i) => {
      cloud.rotation.y += speed * (0.5 + (i % 3) * 0.2) * audioMultiplier;
      cloud.rotation.x -= speed * 0.2 * audioMultiplier;
    });

    innerWireframe.rotation.y += speed * 1.2 * audioMultiplier;
    innerWireframe.rotation.x += speed * 0.8 * audioMultiplier;
    outerWireframe.rotation.y -= speed * 0.9 * audioMultiplier;
    outerWireframe.rotation.z += speed * 0.5 * audioMultiplier;
    ringsGroup.rotation.y += speed * 1.5 * audioMultiplier;
    particles.rotation.y -= speed * 0.4 * audioMultiplier;
    dustPoints.rotation.y += speed * 0.2;

    const pulseFactor = Math.sin(time * pulse * 3) * 0.06 + (audioActive ? 0.15 : 0);
    const coreScale = 1 + pulseFactor;
    coreMesh.scale.set(coreScale, coreScale, coreScale);
    const haloPulse = 1 + Math.sin(time * 2.8) * 0.05;
    multiverseRimHalo.scale.set(haloPulse, haloPulse, haloPulse);

    controls.update();
    composer.render();
  }

  animate();
  window.addEventListener("resize", () => {
    const w = container.clientWidth || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;
    camera.aspect = w / h; camera.updateProjectionMatrix();
    renderer.setSize(w, h); composer.setSize(w, h);
  });

  return {
    rotateBy(dx: number, dy: number) { controls.rotateLeft(dx); controls.rotateUp(dy); controls.update(); },
    zoomBy(f: number) { /* omitted for brevity */ },
    zoomIn() {}, zoomOut() {}, resetView() {},
    setStatus(status: OrbStatus) { 
      currentStatus = status; 
      if (status === 'speaking') {
         updateColors(0x0a84ff, 0x00f0ff);
      } else if (status === 'listening') {
         updateColors(0x30d158, 0x0a84ff);
      } else if (status === 'processing') {
         updateColors(0xbf5af2, 0xc084fc);
      } else {
         updateColors(0x00f0ff, 0x8b5cf6);
      }
    },
    setDynamics(s: number, p: number, a: boolean) {},
    updateColors(p: number, s: number) {
      primaryColorHex = p; secondaryColorHex = s;
      innerLineMaterial.color.setHex(p); outerLineMaterial.color.setHex(s);
      particleMaterial.color.setHex(p);
      fresnelShaderMaterial.uniforms.uColor.value.setHex(p);
      proceduralDotShaderMaterial.uniforms.uPrimaryColor.value.setHex(p);
      proceduralDotShaderMaterial.uniforms.uSecondaryColor.value.setHex(s);
    },
    resize(w: number, h: number) { },
    getCameraDistance() { return 4.2; },
    dispose() { disposed = true; }
  };
}

export interface OrbSceneConfig {
  primaryColorHex: number;
  secondaryColorHex: number;
  rotationSpeed: number;
  pulseHz: number;
  isAudioActive: boolean;
}

export class VictorOrb3DScene {
  private api: OrbSceneApi;
  constructor(container: HTMLElement, initialConfig: OrbSceneConfig) {
    this.api = createOrbScene(container, initialConfig.primaryColorHex);
  }
  setStatus(status: OrbStatus) {
    this.api.setStatus(status);
  }
}

// Global hook for the Python WebView to initialize and control
if (typeof window !== 'undefined') {
  (window as any).initOrb = function(containerId: string) {
    const container = document.getElementById(containerId);
    (window as any).victorOrb = new VictorOrb3DScene(container, {
      primaryColorHex: 0x00f0ff,
      secondaryColorHex: 0x8b5cf6,
      rotationSpeed: 0.006,
      pulseHz: 2.0,
      isAudioActive: false
    });
  };
}
