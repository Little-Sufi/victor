
"""
Advanced Microphone Test Tool for VICTOR
Lets you choose which microphone to use!
"""
import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import speech_recognition as sr
    print("SpeechRecognition library available!")
except ImportError:
    print("ERROR: SpeechRecognition not installed!")
    sys.exit(1)

print("\n" + "="*80)
print("VICTOR ADVANCED MICROPHONE TEST")
print("="*80)

r = sr.Recognizer()
r.energy_threshold = 100
r.dynamic_energy_threshold = True

print("\nListing available microphones...")
mic_list = sr.Microphone.list_microphone_names()
print(f"\nFound {len(mic_list)} microphones:")

input_mics = []
for i, name in enumerate(mic_list):
    if "input" in name.lower() or "microphone" in name.lower() or "headset" in name.lower():
        input_mics.append((i, name))
        print(f"  [{len(input_mics)-1}] ID {i}: {name}")

if not input_mics:
    print("\nERROR: No input microphones found!")
    sys.exit(1)

print("\n" + "="*80)
print("CHOOSE A MICROPHONE:")
print("="*80)
print("\nEnter the number of the microphone you want to test:")

try:
    choice = int(input("\nEnter number (0-" + str(len(input_mics)-1) + "): "))
    if choice < 0 or choice >= len(input_mics):
        print("Invalid choice!")
        sys.exit(1)
except:
    print("Invalid input!")
    sys.exit(1)

mic_id, mic_name = input_mics[choice]
print(f"\nSelected microphone: [{mic_id}] {mic_name}")

print("\n" + "="*80)
print("TESTING - SAY SOMETHING CLEARLY NOW!")
print("="*80)
print("\nTry saying: 'Hey Victor, what time is it?'")
print("\nOr just say any sentence clearly!\n")

try:
    with sr.Microphone(device_index=mic_id) as source:
        print("Adjusting for ambient noise (2 seconds)...")
        r.adjust_for_ambient_noise(source, duration=2)
        print(f"Energy threshold set to: {r.energy_threshold}")
        print("\nListening... (please speak now!)")
        audio = r.listen(source, timeout=15, phrase_time_limit=15)
        print("\nProcessing...")
        text = r.recognize_google(audio)
        print("\n" + "="*80)
        print("SUCCESS! HEARD YOU SAY:")
        print("="*80)
        print(f"\n{text}")
        print("\n" + "="*80)
        print("MICROPHONE IS WORKING PERFECTLY!")
        print("="*80)
        print("\nGreat! Now you can use Victor's voice commands!")

except sr.WaitTimeoutError:
    print("\nERROR: Listen timeout - didn't hear anything!")
    print("\nPossible causes:")
    print("  - Microphone not plugged in")
    print("  - Microphone is muted")
    print("  - No microphone access granted to this app")
    print("  - You didn't speak")
    print("\nCheck Windows Settings > Privacy & security > Microphone!")

except sr.UnknownValueError:
    print("\nHeard audio, but couldn't understand it!")
    print("\nPossible causes:")
    print("  - Too much background noise")
    print("  - Spoke too softly")
    print("  - Spoke too fast")
    print("  - Didn't speak clearly")
    print("\nTry again, speak clearly and at normal volume!")

except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()

print("\nTest complete!")

