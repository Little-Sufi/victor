
"""
Simple Microphone Test Tool for VICTOR
Just tests if microphone is working!
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    import speech_recognition as sr
    print("SpeechRecognition library available!")
except ImportError:
    print("ERROR: SpeechRecognition not installed!")
    sys.exit(1)

print("\n" + "="*80)
print("VICTOR MICROPHONE TEST")
print("="*80)

r = sr.Recognizer()
r.energy_threshold = 100
r.dynamic_energy_threshold = True

print("\nListing available microphones...")
mic_list = sr.Microphone.list_microphone_names()
print(f"\nFound {len(mic_list)} microphones:")
for i, name in enumerate(mic_list):
    print(f"  {i}. {name}")

print("\n" + "="*80)
print("TESTING MICROPHONE - SAY SOMETHING NOW!")
print("="*80)

try:
    with sr.Microphone() as source:
        print("\nListening... (please speak now!)")
        r.adjust_for_ambient_noise(source, duration=1)
        audio = r.listen(source, timeout=10, phrase_time_limit=5)
        print("\nProcessing...")
        text = r.recognize_google(audio)
        print("\n" + "="*80)
        print("SUCCESS! HEARD YOU SAY:")
        print("="*80)
        print(f"\n{text}")
        print("\n" + "="*80)
        print("MICROPHONE IS WORKING PERFECTLY!")
        print("="*80)

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

except Exception as e:
    print(f"\nERROR: {str(e)}")
    print("\nSomething went wrong! Please check your microphone!")

print("\nTest complete!")

