#!/usr/bin/env python3
"""
Voice Assistant Module for Bible Clock
Professional voice interaction with interrupt handling, VAD, and performance metrics
"""

import os
import sys
import logging
import speech_recognition as sr
import time as time_module
import subprocess
import tempfile
from pathlib import Path
from dotenv import load_dotenv
import numpy as np
import threading
import queue
import contextlib

# Suppress ALSA error messages
os.environ['ALSA_QUIET'] = '1'
os.environ['ALSA_CARD'] = os.getenv('ALSA_CARD', '1')
os.environ['PULSE_RUNTIME_PATH'] = '/dev/null'
os.environ['JACK_NO_START_SERVER'] = '1'

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class VoiceAssistant:
    """Professional voice assistant with wake word detection, VAD, and streaming responses."""
    
    def __init__(self, verse_manager=None, visual_feedback_callback=None):
        """Initialize the voice assistant.
        
        Args:
            verse_manager: Optional verse manager for Bible context
            visual_feedback_callback: Function to call for visual state updates
        """
        self.enabled = os.getenv('ENABLE_CHATGPT_VOICE', 'true').lower() == 'true'
        self.voice_timeout = int(os.getenv('VOICE_TIMEOUT', '10'))
        
        # Audio device configuration
        self.usb_speaker_device = 'plughw:2,0'
        self.usb_mic_device = 'plughw:1,0'
        
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
        self.verse_manager = verse_manager
        self.recognizer = None
        self.openai_client = None
        self.porcupine = None
        self.pyaudio = None
        self.usb_mic_index = None
        self.mic_sample_rate = None
        
        # Visual feedback
        self.visual_feedback = visual_feedback_callback
        
        # TTS queue for preventing overlapping speech
        self.tts_queue = queue.Queue()
        self.tts_thread = None
        self.tts_thread_running = False
        self.tts_interrupt_event = threading.Event()
        
        # Performance metrics
        self.metrics = {
            'wake_word_time': None,
            'command_start_time': None,
            'command_end_time': None,
            'gpt_start_time': None,
            'gpt_first_response_time': None,
            'first_speech_time': None
        }
        
        # Interrupt detection
        self.interrupt_detection_active = False
        self.interrupt_thread = None
        
        # Audio device lock to prevent simultaneous access
        self.audio_lock = threading.Lock()
        
        if self.enabled:
            self._initialize_components()
    
    def _update_visual_state(self, state, message=None):
        """Update visual feedback if callback is provided."""
        if self.visual_feedback:
            try:
                self.visual_feedback(state, message)
            except Exception as e:
                logger.warning(f"Visual feedback error: {e}")
    
    def _initialize_components(self):
        """Initialize all voice control components with error handling."""
        try:
            self._update_visual_state("initializing", "Starting voice system...")
            
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
            self._update_visual_state("ready", "Voice assistant ready")
            return True
            
        except Exception as e:
            logger.error(f"Voice system initialization failed: {e}")
            self.enabled = False
            self._update_visual_state("error", f"Init failed: {str(e)}")
            return False
    
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
            
            if len(access_key) < 10:
                logger.error("PICOVOICE_ACCESS_KEY appears to be invalid (too short)")
                logger.info("Access key should start with something like 'picovoice-...'")
                return False
            
            # Initialize Porcupine with custom "Bible Clock" wake word
            self.porcupine = pvporcupine.create(
                access_key=access_key,
                keyword_paths=[str(bible_clock_ppn)],
                sensitivities=[0.5]
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
            
            # Start TTS worker thread
            self._start_tts_worker()
            
            return True
            
        except Exception as e:
            logger.error(f"Porcupine initialization failed: {e}")
            logger.info("Falling back to Google Speech Recognition for wake word")
            self.porcupine = None
            return False
    
    def _initialize_openai_client(self):
        """Initialize OpenAI client with version compatibility."""
        try:
            # Try modern OpenAI API (1.0+)
            from openai import OpenAI
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
                        continue
            
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
                            format=self.pyaudio.get_format_from_width(2),
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
    
    def listen_for_wake_word(self):
        """Listen for wake word using Porcupine (preferred) or Google Speech Recognition (fallback)."""
        self._update_visual_state("listening", "Listening for 'Bible Clock'...")
        
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
                    rate=self.mic_sample_rate,
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
                            # Record wake word detection time
                            self._reset_metrics()
                            self.metrics['wake_word_time'] = time_module.time()
                            self._update_visual_state("wake_detected", "Wake word detected!")
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
                            self._reset_metrics()
                            self.metrics['wake_word_time'] = time_module.time()
                            self._update_visual_state("wake_detected", "Wake word detected!")
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
    
    def _detect_silence(self, audio_chunk, silence_threshold=500):
        """Simple VAD using RMS energy detection."""
        rms = np.sqrt(np.mean(audio_chunk.astype(np.float64) ** 2))
        return rms < silence_threshold
    
    def listen_for_command(self):
        """Listen for voice command with VAD-based automatic end detection."""
        try:
            import pyaudio
            import wave
            
            self._update_visual_state("recording", "Recording command...")
            print("🎤 Listening... speak your command now!")
            
            # Record command start time
            self.metrics['command_start_time'] = time_module.time()
            
            # Audio recording parameters - use mic's native rate
            mic_sample_rate = self.mic_sample_rate  # Use detected mic rate (48kHz)
            target_sample_rate = 16000  # For speech recognition
            chunk_size = 1024
            silence_threshold = 500
            min_silence_duration = 0.8
            max_recording_duration = 10
            
            audio_chunks = []
            silence_chunks = 0
            silence_chunks_needed = int(min_silence_duration * mic_sample_rate / chunk_size)
            total_chunks = 0
            max_chunks = int(max_recording_duration * mic_sample_rate / chunk_size)
            
            # Create audio stream at mic's native sample rate
            with self._suppress_alsa_messages():
                stream = self.pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=mic_sample_rate,  # Use mic's native rate
                    input=True,
                    input_device_index=self.usb_mic_index,
                    frames_per_buffer=chunk_size
                )
            
            logger.info("Recording with VAD - speak now...")
            recording_started = False
            
            while total_chunks < max_chunks:
                # Read audio chunk
                audio_data = stream.read(chunk_size, exception_on_overflow=False)
                audio_chunk = np.frombuffer(audio_data, dtype=np.int16)
                
                # Detect if this chunk contains speech
                is_silent = self._detect_silence(audio_chunk, silence_threshold)
                
                if not is_silent:
                    # Speech detected
                    recording_started = True
                    silence_chunks = 0
                    audio_chunks.append(audio_data)
                elif recording_started:
                    # Silence after speech started
                    silence_chunks += 1
                    audio_chunks.append(audio_data)
                    
                    # Check if we've had enough silence to end recording
                    if silence_chunks >= silence_chunks_needed:
                        logger.info("Silence detected, ending recording")
                        break
                
                total_chunks += 1
            
            stream.stop_stream()
            stream.close()
            
            if not audio_chunks:
                self._update_visual_state("error", "No speech detected")
                print("❓ No speech detected")
                return None
            
            # Combine all audio chunks
            combined_audio = b''.join(audio_chunks)
            
            # Convert audio to numpy array for resampling
            audio_array = np.frombuffer(combined_audio, dtype=np.int16)
            
            # Resample from mic rate to target rate for speech recognition
            if mic_sample_rate != target_sample_rate:
                resampled_audio = self._resample_audio_chunk(
                    audio_array, mic_sample_rate, target_sample_rate
                )
                resampled_bytes = resampled_audio.astype(np.int16).tobytes()
            else:
                resampled_bytes = combined_audio
            
            # Convert to speech recognition format
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
                
                # Write WAV file at 16kHz for speech recognition
                with wave.open(temp_path, 'wb') as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(target_sample_rate)  # 16kHz for speech recognition
                    wav_file.writeframes(resampled_bytes)
            
            self._update_visual_state("processing", "Processing command...")
            
            # Use speech recognition on the recorded file
            with sr.AudioFile(temp_path) as source:
                audio = self.recognizer.record(source)
            
            command = self.recognizer.recognize_google(audio).lower()
            print(f"✅ Command: '{command}'")
            
            # Record command end time
            self.metrics['command_end_time'] = time_module.time()
            
            # Clean up
            os.unlink(temp_path)
            return command
            
        except sr.UnknownValueError:
            self._update_visual_state("error", "Couldn't understand")
            print("❓ Couldn't understand - try speaking more clearly")
            return None
        except sr.RequestError as e:
            self._update_visual_state("error", f"Recognition error: {str(e)}")
            print(f"❌ Recognition error: {e}")
            return None
        except Exception as e:
            self._update_visual_state("error", f"Error: {str(e)}")
            print(f"❌ Error: {e}")
            return None
    
    def get_current_metrics(self):
        """Get current performance metrics."""
        return self.metrics.copy()
    
    def run_main_loop(self):
        """Main voice interaction loop."""
        try:
            while True:
                # Wait for wake word
                if self.listen_for_wake_word():
                    # Wake word detected, listen for command
                    command = self.listen_for_command()
                    if command:
                        self.process_voice_command(command)
        except KeyboardInterrupt:
            self._update_visual_state("shutdown", "Voice assistant stopped")
            logger.info("Voice assistant stopped by user")
        except Exception as e:
            self._update_visual_state("error", f"Main loop error: {str(e)}")
            logger.error(f"Main loop error: {e}")
    
    def _start_interrupt_detection(self):
        """Start background thread to detect wake word interrupts during TTS."""
        if self.porcupine and not self.interrupt_detection_active:
            self.interrupt_detection_active = True
            self.interrupt_thread = threading.Thread(target=self._interrupt_detector, daemon=True)
            self.interrupt_thread.start()
            logger.info("Interrupt detection started")
    
    def _stop_interrupt_detection(self):
        """Stop interrupt detection."""
        self.interrupt_detection_active = False
    
    def _interrupt_detector(self):
        """Background thread that listens for wake word to interrupt current TTS."""
        try:
            import pyaudio
            
            # Calculate frame sizes for resampling
            mic_frame_size = int(self.porcupine.frame_length * self.mic_sample_rate / self.porcupine.sample_rate)
            
            # Create audio stream at mic's native sample rate
            with self._suppress_alsa_messages():
                audio_stream = self.pyaudio.open(
                    rate=self.mic_sample_rate,
                    channels=1,
                    format=pyaudio.paInt16,
                    input=True,
                    input_device_index=self.usb_mic_index,
                    frames_per_buffer=mic_frame_size
                )
            
            while self.interrupt_detection_active:
                try:
                    # Read audio at mic's native rate
                    pcm_bytes = audio_stream.read(mic_frame_size, exception_on_overflow=False)
                    pcm_array = np.frombuffer(pcm_bytes, dtype=np.int16)
                    
                    # Resample to Porcupine's required rate
                    resampled = self._resample_audio_chunk(
                        pcm_array, self.mic_sample_rate, self.porcupine.sample_rate
                    )
                    
                    if len(resampled) >= self.porcupine.frame_length:
                        frame = resampled[:self.porcupine.frame_length]
                        keyword_index = self.porcupine.process(frame.tolist())
                        
                        if keyword_index >= 0:
                            logger.info("🔥 Interrupt detected! Canceling current response...")
                            self._update_visual_state("interrupted", "Interrupted - new command")
                            # Signal TTS to stop and clear queue
                            self.tts_interrupt_event.set()
                            # Clear the TTS queue
                            while not self.tts_queue.empty():
                                try:
                                    self.tts_queue.get_nowait()
                                except queue.Empty:
                                    break
                            # Reset metrics for new interaction
                            self._reset_metrics()
                            self.metrics['wake_word_time'] = time_module.time()
                            # Stop interrupt detection temporarily
                            self._stop_interrupt_detection()
                            # Handle new command
                            command = self.listen_for_command()
                            if command:
                                self.process_voice_command(command)
                            return
                        
                except Exception as e:
                    logger.warning(f"Interrupt detection error: {e}")
                    continue
            
            audio_stream.stop_stream()
            audio_stream.close()
            
        except Exception as e:
            logger.error(f"Interrupt detection failed: {e}")
    
    def _start_tts_worker(self):
        """Start the TTS worker thread to prevent overlapping speech."""
        self.tts_thread_running = True
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.tts_thread.start()
        logger.info("TTS worker thread started")
    
    def _reset_metrics(self):
        """Reset performance metrics for new interaction."""
        for key in self.metrics:
            self.metrics[key] = None
    
    def _log_metrics(self):
        """Log performance metrics."""
        try:
            if self.metrics['wake_word_time'] and self.metrics['first_speech_time']:
                total_time = self.metrics['first_speech_time'] - self.metrics['wake_word_time']
                
                timings = {
                    'wake_to_command': None,
                    'command_duration': None,
                    'gpt_response_time': None,
                    'gpt_to_speech': None,
                    'total_interaction': total_time
                }
                
                if self.metrics['command_start_time']:
                    timings['wake_to_command'] = self.metrics['command_start_time'] - self.metrics['wake_word_time']
                
                if self.metrics['command_end_time'] and self.metrics['command_start_time']:
                    timings['command_duration'] = self.metrics['command_end_time'] - self.metrics['command_start_time']
                
                if self.metrics['gpt_first_response_time'] and self.metrics['gpt_start_time']:
                    timings['gpt_response_time'] = self.metrics['gpt_first_response_time'] - self.metrics['gpt_start_time']
                
                if self.metrics['first_speech_time'] and self.metrics['gpt_first_response_time']:
                    timings['gpt_to_speech'] = self.metrics['first_speech_time'] - self.metrics['gpt_first_response_time']
                
                logger.info("📊 Performance Metrics:")
                logger.info(f"  Total interaction: {total_time:.2f}s")
                if timings['wake_to_command']:
                    logger.info(f"  Wake → Command: {timings['wake_to_command']:.2f}s")
                if timings['command_duration']:
                    logger.info(f"  Command duration: {timings['command_duration']:.2f}s")
                if timings['gpt_response_time']:
                    logger.info(f"  GPT response: {timings['gpt_response_time']:.2f}s")
                if timings['gpt_to_speech']:
                    logger.info(f"  GPT → Speech: {timings['gpt_to_speech']:.2f}s")
                
                return timings
                
        except Exception as e:
            logger.error(f"Metrics logging error: {e}")
        return None
    
    def _tts_worker(self):
        """Worker thread that processes TTS queue to prevent overlapping speech."""
        while self.tts_thread_running:
            try:
                # Get next TTS task from queue (blocks until available)
                tts_text = self.tts_queue.get(timeout=1.0)
                if tts_text is None:  # Shutdown signal
                    break
                
                # Check for interrupt before speaking
                if self.tts_interrupt_event.is_set():
                    self.tts_interrupt_event.clear()
                    logger.info("TTS interrupted, skipping queued message")
                    self.tts_queue.task_done()
                    continue
                
                # Record first speech time for metrics
                if self.metrics['first_speech_time'] is None:
                    self.metrics['first_speech_time'] = time_module.time()
                
                # Update visual state
                self._update_visual_state("speaking", f"Speaking: {tts_text[:30]}...")
                
                # Temporarily disable interrupt detection to avoid mic conflicts
                # TODO: Implement proper audio device sharing in future version
                # self._start_interrupt_detection()
                
                # Speak the text (this will block until complete)
                self._speak_with_amy_direct(tts_text)
                
                # self._stop_interrupt_detection()
                
                # Mark task as done
                self.tts_queue.task_done()
                
                # Log metrics if this was the first speech
                if self.metrics['first_speech_time'] and not hasattr(self, '_metrics_logged'):
                    self._log_metrics()
                    self._metrics_logged = True
                
                # Update visual state back to ready
                self._update_visual_state("ready", "Voice assistant ready")
                
            except queue.Empty:
                continue  # Timeout, check if still running
            except Exception as e:
                logger.error(f"TTS worker error: {e}")
    
    def queue_tts(self, text, priority=False):
        """Queue text for TTS to prevent overlapping speech."""
        try:
            if priority:
                # Clear queue and add this as priority
                while not self.tts_queue.empty():
                    try:
                        self.tts_queue.get_nowait()
                    except queue.Empty:
                        break
            
            self.tts_queue.put(text)
            logger.debug(f"Queued TTS: {text[:50]}...")
            
        except Exception as e:
            logger.error(f"Error queuing TTS: {e}")
    
    def _speak_with_amy_direct(self, text):
        """Direct TTS without queueing (used by worker thread)."""
        try:
            logger.info(f"Speaking: {text[:50]}...")
            
            # Set lower process priority to prevent system lockup on Pi 3B+
            current_priority = os.nice(0)
            os.nice(5)
            
            # Create temporary audio file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Generate audio with Piper - balanced speed and CPU optimization
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
    
    def speak_with_amy(self, text, priority=False):
        """Queue text for TTS to prevent overlapping speech."""
        self.queue_tts(text, priority=priority)
    
    def query_chatgpt(self, question):
        """Send question to ChatGPT using streaming API for real-time responses."""
        try:
            if not self.openai_client:
                return "I need an OpenAI API key to answer questions. Please configure it in your environment."
            
            self._update_visual_state("thinking", "Asking ChatGPT...")
            
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
            
            # Record GPT start time
            self.metrics['gpt_start_time'] = time_module.time()
            
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
                        
                        # Record first response time
                        if self.metrics['gpt_first_response_time'] is None:
                            self.metrics['gpt_first_response_time'] = time_module.time()
                        
                        # Queue complete sentences as they arrive
                        if any(punct in sentence_buffer for punct in ['.', '!', '?', '\n']):
                            sentence = sentence_buffer.strip()
                            if sentence:
                                # Queue this sentence (will be spoken in order)
                                self.queue_tts(sentence)
                            sentence_buffer = ""
                
                # Queue any remaining text
                if sentence_buffer.strip():
                    self.queue_tts(sentence_buffer.strip())
                
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
            error_msg = f"I'm sorry, I encountered an error processing your question: {str(e)}"
            self._update_visual_state("error", error_msg)
            return error_msg
    
    def process_voice_command(self, command_text):
        """Process the voice command."""
        try:
            self._update_visual_state("processing", f"Processing: {command_text}")
            
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
                return  # Exit early for ChatGPT responses
            
            # For built-in commands, speak the response
            if response:
                self.speak_with_amy(response, priority=True)
                
        except Exception as e:
            logger.error(f"Command processing error: {e}")
            error_msg = "I'm sorry, I encountered an error processing your request."
            self._update_visual_state("error", error_msg)
            self.speak_with_amy(error_msg, priority=True)