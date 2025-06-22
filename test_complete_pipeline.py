  import speech_recognition as sr
  import openai
  import subprocess
  import tempfile
  import wave
  import os
  from pathlib import Path

  def test_complete_pipeline():
      print("Testing complete voice pipeline...")

      # Set up OpenAI
      openai.api_key = 'sk-proj-6vl3qzA_-MjgG4pRW2Nl4mlMHgXkYQIvVB7b-rSW88ztUGx3lprc98vqlWKNTABr7__5tYq23UT3BlbkFJY
  NdOkT9d8FmHYmfUCDw2KZ6X-CSCCs3kO1vZ5D_knhbX6YLHIRxf8K2EeFXlCrLZYNbOw9hsAA'

      # Speech to text
      print("1. Converting speech to text...")
      r = sr.Recognizer()
      with wave.open('speech_test.wav', 'rb') as audio_file:
          audio_data = sr.AudioData(
              audio_file.readframes(audio_file.getnframes()),
              audio_file.getframerate(),
              audio_file.getsampwidth()
          )

      text = r.recognize_google(audio_data)
      print(f"   You said: {text}")

      # Send to ChatGPT
      print("2. Sending to ChatGPT...")
      response = openai.ChatCompletion.create(
          model='gpt-3.5-turbo',
          messages=[
              {'role': 'system', 'content': 'You are a helpful Bible study assistant. Keep responses concise.'},
              {'role': 'user', 'content': text}
          ],
          max_tokens=100
      )

      answer = response.choices[0].message.content
      print(f"   ChatGPT response: {answer}")

      # Convert to speech with Piper
      print("3. Converting to speech with Piper...")
      model_path = Path.home() / '.local' / 'share' / 'piper' / 'voices' / 'en_US-amy-medium.onnx'

      with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
          result = subprocess.run([
              'piper',
              '--model', str(model_path),
              '--output_file', temp_file.name
          ], input=answer, text=True)

          if result.returncode == 0:
              print("4. Playing response...")
              subprocess.run(['aplay', temp_file.name])
              print("✅ Complete pipeline successful!")
          else:
              print("❌ Piper TTS failed")

          # Clean up
          try:
              os.unlink(temp_file.name)
          except:
              pass

  if __name__ == "__main__":
      test_complete_pipeline()
  EOF
