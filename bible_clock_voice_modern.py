#!/usr/bin/env python3
"""
Bible Clock Voice Control - Modern API Compatible Version
Updated for OpenAI API 1.0+ compatibility with automatic version management
"""

import os
import sys
import logging
import speech_recognition as sr
import time
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv

# Suppress ALSA error messages
os.environ['ALSA_QUIET'] = '1'

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ModernBibleClockVoice:
    def __init__(self):
        """Initialize the modern voice control system."""
        self.enabled = os.getenv('ENABLE_CHATGPT_VOICE', 'true').lower() == 'true'
        self.voice_timeout = int(os.getenv('VOICE_TIMEOUT', '10'))
        
        # Audio device configuration
        self.usb_speaker_device = 'plughw:2,0'  # UACDemoV1.0 speakers
        self.usb_mic_device = 'plughw:1,0'  # USB PnP Audio Device
        
        # API configuration
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        self.chatgpt_model = os.getenv('CHATGPT_MODEL', 'gpt-3.5-turbo')
        self.max_tokens = int(os.getenv('CHATGPT_MAX_TOKENS', '150'))
        self.system_prompt = os.getenv('CHATGPT_SYSTEM_PROMPT', 
            'You are a knowledgeable Bible study assistant. Provide accurate, thoughtful responses about the Bible, Christianity, and faith. Keep responses concise and meaningful, suitable for voice interaction.')
        
        # Wake word configuration
        self.wake_word = 'Bible Clock'
        
        # Piper TTS configuration
        self.piper_model_path = os.path.expanduser('~/.local/share/piper/voices/en_US-amy-medium.onnx')
        
        # Voice components
        self.verse_manager = None
        self.recognizer = None
        self.openai_client = None
        
        if self.enabled:
            self._initialize_components()
    
    def _initialize_components(self):
        """Initialize all voice control components with error handling."""
        try:
            # Initialize verse manager
            from src.verse_manager import VerseManager
            self.verse_manager = VerseManager()
            logger.info("Verse manager initialized")
            
            # Initialize speech recognition
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
            self.recognizer.operation_timeout = self.voice_timeout
            logger.info("Speech recognizer initialized")
            
            logger.info(f"Wake word detection ready for '{self.wake_word}'")
            
            # Test Piper TTS
            if not Path(self.piper_model_path).exists():
                logger.error(f"Amy voice model not found: {self.piper_model_path}")
                return False
            
            # Initialize OpenAI client (modern API)
            if self.openai_api_key:
                self._initialize_openai_client()
                logger.info("OpenAI client initialized with modern API")
            else:
                logger.warning("No OpenAI API key configured")
            
            logger.info("All voice components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Voice system initialization failed: {e}")
            self.enabled = False
            return False
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client with version compatibility."""
        try:
            # Try modern OpenAI API (1.0+)
            from openai import OpenAI
            # Remove any problematic proxy arguments
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            self.api_version = "modern"
            logger.info("Using modern OpenAI API (1.0+)")
        except Exception as e:
            logger.warning(f"Modern OpenAI API failed: {e}")
            try:
                # Fallback to legacy API
                import openai
                openai.api_key = self.openai_api_key
                self.openai_client = openai
                self.api_version = "legacy"
                logger.info("Using legacy OpenAI API (0.28)")
            except Exception as e2:
                logger.error(f"Failed to initialize OpenAI: {e2}")
                self.openai_client = None
    
    def speak_with_amy(self, text):
        """Convert text to speech using Piper Amy voice with correct audio routing."""
        try:
            logger.info(f"Speaking: {text[:50]}...")
            
            # Create temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Generate audio with Piper
            result = subprocess.run([
                'piper',
                '--model', self.piper_model_path,
                '--output_file', temp_path
            ], input=text, text=True, capture_output=True)
            
            if result.returncode == 0:
                # Play audio through correct USB speakers
                subprocess.run(['aplay', '-D', self.usb_speaker_device, temp_path], 
                             capture_output=True)
                logger.info("Audio played successfully")
            else:
                logger.error(f"Piper TTS failed: {result.stderr}")
            
            # Clean up
            os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
    
    def query_chatgpt(self, question):
        """Send question to ChatGPT using version-compatible API."""
        try:
            if not self.openai_client:
                return "I need an OpenAI API key to answer questions. Please configure it in your environment."
            
            # Get current verse context
            current_verse = ""
            if self.verse_manager:
                verse_data = self.verse_manager.get_current_verse()
                if verse_data:
                    current_verse = f"Current verse displayed: {verse_data.get('reference', '')} - {verse_data.get('text', '')}"
            
            # Create system prompt with current verse context
            full_system_prompt = f"""{self.system_prompt}
            
{current_verse}

When asked to "explain this verse" or similar, refer to the current verse displayed above."""
            
            # Use appropriate API version
            if self.api_version == "modern":
                response = self.openai_client.chat.completions.create(
                    model=self.chatgpt_model,
                    messages=[
                        {"role": "system", "content": full_system_prompt},
                        {"role": "user", "content": question}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.7
                )
                answer = response.choices[0].message.content.strip()
            else:
                # Legacy API
                response = self.openai_client.ChatCompletion.create(
                    model=self.chatgpt_model,
                    messages=[
                        {"role": "system", "content": full_system_prompt},
                        {"role": "user", "content": question}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.7
                )
                answer = response.choices[0].message.content.strip()
            
            logger.info(f"ChatGPT response: {answer[:100]}...")
            return answer
            
        except Exception as e:
            logger.error(f"ChatGPT query failed: {e}")
            return f"I'm sorry, I encountered an error processing your question: {str(e)}"
    
    def process_voice_command(self, command_text):
        """Process the voice command."""
        try:
            # Built-in commands
            if any(word in command_text for word in ['help', 'commands']):
                response = "I can help with Bible questions, verses, and basic commands. Try asking: What does John 3:16 say? Or say next verse, previous verse, or refresh display."
                
            elif 'next verse' in command_text or 'next' in command_text:
                if self.verse_manager:
                    self.verse_manager.next_verse()
                    current_verse = self.verse_manager.get_current_verse()
                    response = f"Next verse: {current_verse.get('reference', '')} - {current_verse.get('text', '')}"
                else:
                    response = "Verse manager not available."
                
            elif 'previous verse' in command_text or 'previous' in command_text:
                if self.verse_manager:
                    self.verse_manager.previous_verse()
                    current_verse = self.verse_manager.get_current_verse()
                    response = f"Previous verse: {current_verse.get('reference', '')} - {current_verse.get('text', '')}"
                else:
                    response = "Verse manager not available."
                
            elif any(phrase in command_text for phrase in ['current verse', 'read verse', 'this verse']):
                if self.verse_manager:
                    current_verse = self.verse_manager.get_current_verse()
                    if current_verse:
                        response = f"{current_verse.get('reference', '')}: {current_verse.get('text', '')}"
                    else:
                        response = "No verse is currently displayed."
                else:
                    response = "Verse manager not available."
                    
            elif any(phrase in command_text for phrase in ['explain this verse', 'explain verse', 'what does this mean', 'explain this']):
                # Send current verse explanation to ChatGPT
                if self.verse_manager:
                    current_verse = self.verse_manager.get_current_verse()
                    if current_verse:
                        explanation_query = f"Explain this Bible verse: {current_verse.get('reference', '')} - {current_verse.get('text', '')}"
                        response = self.query_chatgpt(explanation_query)
                    else:
                        response = "No verse is currently displayed to explain."
                else:
                    response = "Verse manager not available."
                
            else:
                # Send to ChatGPT for Bible questions
                response = self.query_chatgpt(command_text)
            
            # Speak the response
            if response:
                self.speak_with_amy(response)
                
        except Exception as e:
            logger.error(f"Command processing error: {e}")
            self.speak_with_amy("I'm sorry, I encountered an error processing your request.")
    
    def listen_for_wake_word(self):
        """Listen for wake word using Google Speech Recognition."""
        try:
            logger.info(f"👂 Listening for wake word '{self.wake_word}'...")
            
            while True:
                # Record 3 seconds of audio
                import subprocess
                import tempfile
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Record from USB microphone - shorter for faster response
                result = subprocess.run([
                    'arecord', '-D', self.usb_mic_device,
                    '-f', 'S16_LE', '-r', '16000', '-c', '1',
                    '-d', '2', temp_path
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Recording failed: {result.stderr}")
                    os.unlink(temp_path)
                    continue
                
                # Use speech recognition to check for wake word
                try:
                    import speech_recognition as sr
                    
                    with sr.AudioFile(temp_path) as source:
                        audio = self.recognizer.record(source)
                    
                    try:
                        text = self.recognizer.recognize_google(audio).lower()
                        logger.info(f"Heard: '{text}'")
                        
                        # Check for wake word variations
                        wake_variations = ['bible clock', 'bible', 'clock']
                        if any(word in text for word in wake_variations):
                            logger.info(f"🎯 Wake word detected in: '{text}'")
                            os.unlink(temp_path)
                            return True
                            
                    except sr.UnknownValueError:
                        pass  # No speech detected
                    except sr.RequestError as e:
                        logger.warning(f"Speech recognition error: {e}")
                        
                except Exception as e:
                    logger.error(f"Wake word check error: {e}")
                
                os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"Wake word detection error: {e}")
            return False
    
    def listen_for_command(self):
        """Listen for a single voice command using ALSA directly."""
        try:
            print("🎤 Listening... speak your command now!")
            
            # Record audio using ALSA directly for better USB mic support
            import subprocess
            import tempfile
            import wave
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Record 5 seconds of audio using arecord
            result = subprocess.run([
                'arecord', '-D', self.usb_mic_device, 
                '-f', 'S16_LE', '-r', '16000', '-c', '1',
                '-d', '5', temp_path
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Recording failed: {result.stderr}")
                os.unlink(temp_path)
                return None
            
            # Use speech recognition on the recorded file
            with sr.AudioFile(temp_path) as source:
                audio = self.recognizer.record(source)
            
            command = self.recognizer.recognize_google(audio).lower()
            print(f"✅ Command: '{command}'")
            
            # Clean up
            os.unlink(temp_path)
            return command
            
        except sr.UnknownValueError:
            print("❓ Couldn't understand - try speaking more clearly")
            return None
        except sr.RequestError as e:
            print(f"❌ Recognition error: {e}")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None

def main():
    """Main function to run the modern voice control system."""
    print("🎤 Bible Clock - Modern Voice Control System")
    print("=" * 60)
    print("✅ Version-compatible OpenAI API")
    print("✅ USB audio device support")
    print("✅ Wake word detection")
    print("✅ Automatic error recovery")
    print("=" * 60)
    
    # Initialize voice system
    voice_system = ModernBibleClockVoice()
    
    if not voice_system.enabled:
        print("❌ Voice control disabled. Check configuration.")
        return
    
    # Wake word is always available with speech recognition
    print(f"🎯 Wake word: '{voice_system.wake_word}'")
    voice_system.speak_with_amy(f"Bible Clock voice control ready. Say {voice_system.wake_word} to activate.")
    wake_word_mode = True
    
    print("\n🎯 VOICE COMMANDS:")
    print("• 'explain this verse' - Current verse explanation")  
    print("• 'what does john 3:16 say' - Bible questions")
    print("• 'next verse' / 'previous verse' - Navigation")
    print("• 'read current verse' - Hear current verse")
    print("• Press Ctrl+C to exit")
    print("=" * 60)
    
    try:
        while True:
            # Wait for wake word
            if voice_system.listen_for_wake_word():
                voice_system.speak_with_amy("Yes?")
                # Listen for command after wake word
                command = voice_system.listen_for_command()
                if command:
                    voice_system.process_voice_command(command)
    
    except KeyboardInterrupt:
        pass
    
    print("\n👋 Bible Clock voice control stopped.")
    try:
        voice_system.speak_with_amy("Goodbye!")
    except:
        pass

if __name__ == "__main__":
    main()