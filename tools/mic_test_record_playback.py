
"""
Super Simple Microphone Test - Records and Plays Back!
Just verifies your microphone is working at all!
"""
import sys
import os
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("\n" + "="*80)
print("SUPER SIMPLE MIC TEST - RECORD & PLAYBACK")
print("="*80)

try:
    import sounddevice as sd
    import soundfile as sf
    import numpy as np
    print("\n✓ sounddevice & soundfile libraries available!")
except ImportError as e:
    print(f"\nERROR: Missing libraries! {e}")
    print("\nInstall them with:")
    print("  pip install sounddevice soundfile numpy")
    sys.exit(1)

print("\nAvailable audio devices:")
devices = sd.query_devices()
input_devices = []
for i, dev in enumerate(devices):
    if dev['max_input_channels'] > 0:
        input_devices.append((i, dev))
        print(f"  [{len(input_devices)-1}] ID {i}: {dev['name']} (in={dev['max_input_channels']})")

if not input_devices:
    print("\nERROR: No input devices found!")
    sys.exit(1)

try:
    choice = int(input("\nChoose device number (0-" + str(len(input_devices)-1) + "): "))
    if choice < 0 or choice >= len(input_devices):
        print("Invalid choice!")
        sys.exit(1)
except:
    print("Invalid input!")
    sys.exit(1)

device_id, dev = input_devices[choice]
print(f"\nSelected: {dev['name']}")

sample_rate = 44100
duration = 5
channels = 1

print("\n" + "="*80)
print(f"RECORDING FOR {duration} SECONDS - SPEAK NOW!")
print("="*80)
print("\nRecording...")
try:
    recording = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=channels,
        device=device_id,
        dtype='float32'
    )
    sd.wait()
    print("✓ Recording done!")
except Exception as e:
    print(f"\nERROR recording: {e}")
    sys.exit(1)

temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
temp_file.close()
sf.write(temp_file.name, recording, sample_rate)
print(f"\nSaved to: {temp_file.name}")

print("\n" + "="*80)
print("PLAYING BACK RECORDING...")
print("="*80)

try:
    data, sr = sf.read(temp_file.name)
    sd.play(data, sr)
    sd.wait()
    print("\n✓ Playback complete!")
except Exception as e:
    print(f"\nERROR playing: {e}")

print("\n" + "="*80)
print("RESULTS:")
print("="*80)
print("\nIf you heard your voice: MIC IS WORKING PERFECTLY!")
print("If you didn't hear anything: Check your mic volume/settings!")
print("\nCleaning up temp file...")
try:
    os.unlink(temp_file.name)
except:
    pass
print("\nTest complete!")

