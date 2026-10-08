# 🎙️ Voice Engine & DSP Audio Architecture

VICTOR's voice pipeline is designed for hyper-realistic character mimicry, sub-second latency, and mechanical leader presence.

---

## 🤖 Optimus Prime DSP Comb-Filter Resonance

By default, VICTOR uses the heroic, baritone leader voice of **Optimus Prime**. To achieve the authentic robotic metallic resonance heard in cinematic films, incoming 24,000Hz 16-bit PCM audio passes through an active DSP processing chain:

1. **Comb Filter Delay**: A delay line of $84$ samples (~3.5ms delay) mixes delayed feedback into the direct audio stream, generating sharp flanger resonances.
2. **Sub-Bass Harmonic Boost**: Enhances low-frequency harmonics (60Hz – 180Hz) for chest-rattling vocal authority.
3. **Dynamic Limiter**: Prevents clipping during impassioned heroic battle cries.

---

## 🎭 Persona Mimicry Library

VICTOR features an extensive voice mimicry library spanning comic icons, anime heroes, and tactical personas:

| Category | Available Personas |
| :--- | :--- |
| **Sci-Fi & Cyber** | **Optimus Prime** (Default), Lord Megatron, Ultron, J.A.R.V.I.S. |
| **Heroes & Anti-Heroes**| Batman (The Dark Knight), Deadpool (Wade Wilson), Drill Sergeant |
| **Anime & Shinobi** | Son Goku, Naruto Uzumaki, Monkey D. Luffy, Killer Bee, Obito Uchiha, Prince Vegeta, Roronoa Zoro, Satoru Gojo |

### Switching Personas Dynamically
Simply ask VICTOR in natural language:
> *"Victor, speak like Deadpool."*  
> *"Victor, switch to Batman mode."*  
> *"Victor, return to Optimus Prime."*
