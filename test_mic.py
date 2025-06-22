import speech_recognition as sr

def test_microphone():
    r = sr.Recognizer()
    print("Testing
  default microphone...")
    
    try:
        mic = sr.Microphone()
        with mic as source:

  print("Adjusting for noise...")
            r.adjust_for_ambient_noise(source, duration=1)

  print("Say something now")
            audio = r.listen(source, timeout=5, phrase_time_limit=3)
        

     text = r.recognize_google(audio)
        print("Success! You said: " + text)
        return True
        

      except Exception as e:
        print("Default mic failed: " + str(e))
        return False

if __name__
  == "__main__":
    test_microphone()
