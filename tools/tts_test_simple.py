
"""
Simple TTS Test for VICTOR - ASCII only
Just tests if TTS is working!
"""
import sys
import os
import tempfile
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("\n" + "="*80)
print("VICTOR TTS TEST")
print("="*80)

try:
    import edge_tts
    print("\n[OK] edge_tts available!")
except ImportError as e:
    print(f"\n[ERROR] edge_tts not installed! {e}")
    sys.exit(1)

try:
    import pygame
    print("[OK] pygame available!")
except ImportError as e:
    print(f"\n[ERROR] pygame not installed! {e}")
    sys.exit(1)

pygame.mixer.init()
print("[OK] pygame mixer initialized!")

text = "Hello! This is Victor, your AI assistant! If you can hear this, the TTS system is working perfectly!"
voice = "en-US-GuyNeural"

print(f"\nGenerating speech with voice: {voice}")
print(f"Text to speak: {text}")

temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.mp3')
temp_file.close()

async def _tts():
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(temp_file.name)

try:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_tts())
    print("[OK] TTS audio generated!")
except Exception as e:
    print(f"\n[ERROR] generating TTS: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print(f"\nSaved to: {temp_file.name}")

print("\n" + "="*80)
print("PLAYING AUDIO NOW...")
print("="*80)

try:
    pygame.mixer.music.load(temp_file.name)
    pygame.mixer.music.play()
    print("Playing...")
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    pygame.mixer.music.unload()
    print("[OK] Playback complete!")
except Exception as e:
    print(f"\n[ERROR] playing audio: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("RESULTS:")
print("="*80)
print("\nIf you heard the audio: TTS SYSTEM IS WORKING PERFECTLY!")
print("If you didn't hear anything: Check your speakers/volume!")

print("\nCleaning up temp file...")
try:
    os.unlink(temp_file.name)
except:
    pass

print("\nTest complete!")

