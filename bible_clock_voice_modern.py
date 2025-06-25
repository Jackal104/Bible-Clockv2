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
import numpy as np
import threading
import queue

# Suppress ALSA error messages
os.environ['ALSA_QUIET'] = '1'
os.environ['ALSA_CARD'] = os.getenv('ALSA_CARD', '1')  # Configurable ALSA card (default USB)
os.environ['PULSE_RUNTIME_PATH'] = '/dev/null'  # Disable PulseAudio
os.environ['JACK_NO_START_SERVER'] = '1'  # Disable JACK

# Redirect stderr to suppress ALSA warnings during PyAudio init
import contextlib
import sys

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
        self.max_tokens = int(os.getenv('CHATGPT_MAX_TOKENS', '50'))
        self.system_prompt = os.getenv('CHATGPT_SYSTEM_PROMPT', 
            'You are a knowledgeable Bible study assistant. Provide accurate, thoughtful responses about the Bible, Christianity, and faith. Keep responses very brief (1-2 sentences max), suitable for voice interaction.')
        
        # Porcupine access key
        self.porcupine_access_key = os.getenv('PICOVOICE_ACCESS_KEY', '')
        
        # Wake word configuration
        self.wake_word = 'Bible Clock'
        
        # Piper TTS configuration
        self.piper_model_path = os.path.expanduser('~/.local/share/piper/voices/en_US-amy-medium.onnx')
        
        # Voice components
        self.verse_manager = None
        self.recognizer = None
        self.openai_client = None
        self.porcupine = None
        
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
            
            # Initialize Porcupine for wake word detection
            self._initialize_porcupine()
            
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
    
    def _initialize_porcupine(self):
        """Initialize Porcupine wake word detection with custom Bible Clock wake word."""
        try:
            import pvporcupine
            import pyaudio
            
            # Path to custom Bible Clock wake word file
            bible_clock_ppn = Path('./Bible-Clock_en_raspberry-pi_v3_0_0.ppn')
            
            if not bible_clock_ppn.exists():
                logger.error(f"Custom Bible Clock wake word file not found: {bible_clock_ppn}")
                return False
            
            # Explicit access key validation
            access_key = os.getenv("PICOVOICE_ACCESS_KEY")
            if not access_key:
                logger.error("Missing PICOVOICE_ACCESS_KEY in .env")
                logger.info("Please add PICOVOICE_ACCESS_KEY to your .env file")
                logger.info("Get your free access key from: https://console.picovoice.ai/")
                return False
            
            if len(access_key) < 10:  # Basic sanity check
                logger.error("PICOVOICE_ACCESS_KEY appears to be invalid (too short)")
                logger.info("Access key should start with something like 'picovoice-...'")
                return False
            
            # Initialize Porcupine with custom "Bible Clock" wake word
            self.porcupine = pvporcupine.create(
                access_key=access_key,                   # Validated access key
                keyword_paths=[str(bible_clock_ppn)],    # Your custom Bible Clock wake word
                sensitivities=[0.5]                      # Medium sensitivity
            )
            
            # Initialize PyAudio with error suppression
            with self._suppress_alsa_messages():
                self.pyaudio = pyaudio.PyAudio()
            
            # Get mic's native sample rate for optimal resampling
            self.mic_sample_rate = self._get_mic_sample_rate()
            logger.info(f"USB mic native sample rate: {self.mic_sample_rate}Hz")
            
            # Find USB microphone device index
            self.usb_mic_index = self._find_usb_mic_device()
            if self.usb_mic_index is None:
                logger.warning("No microphone found, using default device 0")
                self.usb_mic_index = 0
            
            logger.info(f"Porcupine initialized - Sample rate: {self.porcupine.sample_rate}Hz")
            logger.info(f"Using USB mic device index: {self.usb_mic_index}")
            logger.info("Using custom 'Bible Clock' wake word model")
            return True
            
        except Exception as e:
            logger.error(f"Porcupine initialization failed: {e}")
            logger.info("Falling back to Google Speech Recognition for wake word")
            self.porcupine = None
            return False
    
    @contextlib.contextmanager
    def _suppress_alsa_messages(self):
        """Proper context manager to suppress ALSA error messages without file handle leaks."""
        with open(os.devnull, 'w') as fnull:
            with contextlib.redirect_stderr(fnull):
                yield
    
    def _find_usb_mic_device(self):
        """Find USB microphone device index in PyAudio with error suppression."""
        try:
            import pyaudio
            
            # Suppress ALSA errors during device enumeration
            with self._suppress_alsa_messages():
                device_count = self.pyaudio.get_device_count()
                
                for i in range(device_count):
                    try:
                        device_info = self.pyaudio.get_device_info_by_index(i)
                        device_name = device_info.get('name', '').lower()
                        
                        # Look for USB audio devices
                        if any(keyword in device_name for keyword in ['usb', 'fifine', 'pnp', 'microphone']):
                            if device_info.get('maxInputChannels', 0) > 0:
                                logger.info(f"Found USB mic: {device_info['name']} (index {i})")
                                return i
                    except Exception:
                        continue  # Skip problematic devices
            
            # If no USB mic found, try to find any input device
            logger.warning("No USB microphone found, looking for any input device...")
            with self._suppress_alsa_messages():
                for i in range(device_count):
                    try:
                        device_info = self.pyaudio.get_device_info_by_index(i)
                        if device_info.get('maxInputChannels', 0) > 0:
                            logger.info(f"No USB mic found. Using fallback input: {device_info['name']} (index {i})")
                            return i
                    except Exception:
                        continue
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding microphone: {e}")
            return None
    
    def _get_mic_sample_rate(self):
        """Detect the native sample rate of the USB microphone."""
        try:
            # Try common sample rates, starting with highest for best quality
            test_rates = [48000, 44100, 32000, 22050, 16000, 8000]
            
            for rate in test_rates:
                try:
                    with self._suppress_alsa_messages():
                        test_stream = self.pyaudio.open(
                            format=self.pyaudio.get_format_from_width(2),  # 16-bit
                            channels=1,
                            rate=rate,
                            input=True,
                            input_device_index=self.usb_mic_index,
                            frames_per_buffer=1024
                        )
                        test_stream.close()
                        logger.info(f"Mic supports sample rate: {rate}Hz")
                        return rate
                except Exception:
                    continue
            
            # Default fallback
            logger.warning("Could not detect mic sample rate, using 48000Hz")
            return 48000
            
        except Exception as e:
            logger.error(f"Error detecting mic sample rate: {e}")
            return 48000
    
    def _resample_audio_chunk(self, audio_chunk, source_rate, target_rate):
        """Fast in-memory audio resampling using numpy interpolation."""
        try:
            if source_rate == target_rate:
                return audio_chunk
            
            # Simple linear interpolation for real-time performance
            ratio = target_rate / source_rate
            original_length = len(audio_chunk)
            new_length = int(original_length * ratio)
            
            # Use numpy for fast resampling
            indices = np.linspace(0, original_length - 1, new_length)
            resampled = np.interp(indices, np.arange(original_length), audio_chunk)
            
            return resampled.astype(np.int16)
            
        except Exception as e:
            logger.error(f"Resampling error: {e}")
            return audio_chunk
    
    def speak_with_amy(self, text):
        """Convert text to speech using Piper Amy voice optimized for Pi 3B+."""
        try:
            logger.info(f"Speaking: {text[:50]}...")
            
            # Set lower process priority to prevent system lockup on Pi 3B+
            current_priority = os.nice(0)
            os.nice(5)
            
            # Create temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Generate audio with Piper - Pi 3B+ optimized (limit to 2 cores)
            result = subprocess.run([
                'taskset', '-c', '0,1',  # Limit to first 2 CPU cores
                'piper',
                '--model', self.piper_model_path,
                '--output_file', temp_path,
                '--length_scale', '0.85',  # Speak 15% faster (more natural)
                '--noise_scale', '0.667',  # Default noise for quality
                '--sentence_silence', '0.2'  # Slightly reduced pauses
            ], input=text, text=True, capture_output=True)
            
            if result.returncode == 0:
                # Play audio through correct USB speakers with maximum speed
                subprocess.run(['aplay', '-D', self.usb_speaker_device, 
                              '--buffer-size=512', '--period-size=256', temp_path], 
                             capture_output=True)
                logger.info("Audio played successfully")
            else:
                logger.error(f"Piper TTS failed: {result.stderr}")
            
            # Clean up
            os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Speech synthesis error: {e}")
    
    def query_chatgpt(self, question):
        """Send question to ChatGPT using streaming API for real-time responses."""
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
            
            # Use streaming for real-time response
            if self.api_version == "modern":
                response_stream = self.openai_client.chat.completions.create(
                    model=self.chatgpt_model,
                    messages=[
                        {"role": "system", "content": full_system_prompt},
                        {"role": "user", "content": question}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=0.7,
                    stream=True  # Enable streaming for real-time response
                )
                
                # Collect response chunks for real-time TTS
                full_response = ""
                sentence_buffer = ""
                
                for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_response += content
                        sentence_buffer += content
                        
                        # Speak complete sentences as they arrive
                        if any(punct in sentence_buffer for punct in ['.', '!', '?', '\n']):
                            sentence = sentence_buffer.strip()
                            if sentence:
                                # Speak this sentence immediately (non-blocking)
                                threading.Thread(target=self.speak_with_amy, args=(sentence,), daemon=True).start()
                            sentence_buffer = ""
                
                # Speak any remaining text
                if sentence_buffer.strip():
                    threading.Thread(target=self.speak_with_amy, args=(sentence_buffer.strip(),), daemon=True).start()
                
                logger.info(f"ChatGPT streaming response: {full_response[:100]}...")
                return full_response
                
            else:
                # Legacy API fallback (non-streaming)
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
                # Send to ChatGPT for Bible questions (streaming will handle TTS automatically)
                response = self.query_chatgpt(command_text)
                # Note: streaming ChatGPT already handles TTS, no need to speak again
                
        except Exception as e:
            logger.error(f"Command processing error: {e}")
            self.speak_with_amy("I'm sorry, I encountered an error processing your request.")
    
    def listen_for_wake_word(self):
        """Listen for wake word using Porcupine (preferred) or Google Speech Recognition (fallback)."""
        if self.porcupine:
            return self._listen_for_wake_word_porcupine()
        else:
            return self._listen_for_wake_word_google()
    
    def _listen_for_wake_word_porcupine(self):
        """Listen for wake word using Porcupine with real-time resampling."""
        try:
            import pyaudio
            
            logger.info("👂 Listening for wake word 'Bible Clock' (Porcupine with resampling)...")
            
            # Calculate frame sizes for resampling
            mic_frame_size = int(self.porcupine.frame_length * self.mic_sample_rate / self.porcupine.sample_rate)
            
            # Create audio stream at mic's native sample rate
            with self._suppress_alsa_messages():
                audio_stream = self.pyaudio.open(
                    rate=self.mic_sample_rate,  # Use mic's native rate
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    input_device_index=self.usb_mic_index,
                    frames_per_buffer=mic_frame_size
                )
            
            logger.info(f"Audio stream: {self.mic_sample_rate}Hz → {self.porcupine.sample_rate}Hz")
            
            while True:
                try:
                    # Read audio at mic's native rate
                    pcm_bytes = audio_stream.read(mic_frame_size, exception_on_overflow=False)
                    
                    # Convert to numpy array
                    pcm_array = np.frombuffer(pcm_bytes, dtype=np.int16)
                    
                    # Resample to Porcupine's required rate (16kHz)
                    resampled = self._resample_audio_chunk(
                        pcm_array, self.mic_sample_rate, self.porcupine.sample_rate
                    )
                    
                    # Ensure we have exactly the right frame size
                    if len(resampled) >= self.porcupine.frame_length:
                        frame = resampled[:self.porcupine.frame_length]
                        
                        # Process with Porcupine
                        keyword_index = self.porcupine.process(frame.tolist())
                        
                        if keyword_index >= 0:
                            logger.info("🎯 Wake word 'Bible Clock' detected by Porcupine!")
                            audio_stream.stop_stream()
                            audio_stream.close()
                            return True
                        
                except Exception as e:
                    logger.warning(f"Porcupine processing error: {e}")
                    continue
                
        except Exception as e:
            logger.error(f"Porcupine wake word detection error: {e}")
            return False
    
    def _listen_for_wake_word_google(self):
        """Fallback wake word detection using Google Speech Recognition."""
        try:
            logger.info(f"👂 Listening for wake word '{self.wake_word}' (Google SR fallback)...")
            
            while True:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                # Record from USB microphone
                result = subprocess.run([
                    'arecord', '-D', self.usb_mic_device,
                    '-f', 'S16_LE', '-r', '16000', '-c', '1',
                    '-d', '2', temp_path
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Recording failed: {result.stderr}")
                    os.unlink(temp_path)
                    continue
                
                try:
                    with sr.AudioFile(temp_path) as source:
                        audio = self.recognizer.record(source)
                    
                    try:
                        text = self.recognizer.recognize_google(audio).lower()
                        logger.info(f"Heard: '{text}'")
                        
                        # Check for wake word variations
                        wake_variations = ['bible clock', 'bible', 'clock', 'computer']
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
    
    # Show active wake word detection method
    if voice_system.porcupine:
        print("🎯 Wake word: 'Bible Clock' (Custom Porcupine Model) - Ready!")
    else:
        print(f"🎯 Wake word: '{voice_system.wake_word}' (Google SR fallback) - Ready!")
    # Skip startup voice message for instant readiness
    
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
                # Skip "Yes?" for instant response - go straight to listening
                print("🎯 Wake word detected! Listening for command...")
                command = voice_system.listen_for_command()
                if command:
                    voice_system.process_voice_command(command)
    
    except KeyboardInterrupt:
        pass
    
    print("\n👋 Bible Clock voice control stopped.")
    # Skip goodbye voice message for faster shutdown

if __name__ == "__main__":
    main()