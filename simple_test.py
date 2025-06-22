  import speech_recognition as sr
  import wave

  r = sr.Recognizer()

  # Read the recorded file
  with wave.open('speech_test.wav', 'rb') as audio_file:
      audio_data = sr.AudioData(audio_file.readframes(audio_file.getnframes()),
                               audio_file.getframerate(),
                               audio_file.getsampwidth())

  try:
      text = r.recognize_google(audio_data)
      print("You said: " + text)
  except Exception as e:
      print("Recognition failed: " + str(e))
  EOF
