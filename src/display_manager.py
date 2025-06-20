"""
Manages e-ink display output and simulation.
"""

import os
import logging
import psutil
from PIL import Image
from typing import Optional
import time

from display_constants import DisplayModes

class DisplayManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.simulation_mode = os.getenv('SIMULATION_MODE', 'false').lower() == 'true'
        self.width = int(os.getenv('DISPLAY_WIDTH', '1872'))
        self.height = int(os.getenv('DISPLAY_HEIGHT', '1404'))
        self.rotation = int(os.getenv('DISPLAY_ROTATION', '0'))
        self.vcom_voltage = float(os.getenv('DISPLAY_VCOM', '-1.21'))
        self.force_refresh_interval = int(os.getenv('FORCE_REFRESH_INTERVAL', '60'))
        
        self.last_image_hash = None
        self.last_full_refresh = time.time()
        self.display_device = None
        
        if not self.simulation_mode:
            self._initialize_hardware()
    
    def _initialize_hardware(self):
        """Initialize the IT8951 e-ink display."""
        try:
            # Import hardware-specific modules
            from IT8951.display import AutoEPDDisplay
            
            self.display_device = AutoEPDDisplay(
                vcom=self.vcom_voltage,  # VCOM voltage from display ribbon
                rotate=self.rotation,
                spi_hz=24000000
            )
            
            self.logger.info(f"E-ink display initialized: {self.width}x{self.height}")
            
        except ImportError:
            self.logger.warning("IT8951 library not available, falling back to simulation")
            self.simulation_mode = True
        except Exception as e:
            self.logger.error(f"Display initialization failed: {e}")
            self.simulation_mode = True
    
    def display_image(self, image: Image.Image, force_refresh: bool = False):
        """Display image on e-ink screen or save for simulation."""
        try:
            # Resize image to display dimensions
            if image.size != (self.width, self.height):
                image = image.resize((self.width, self.height), Image.Resampling.LANCZOS)
            
            # Convert to grayscale for e-ink
            if image.mode != 'L':
                image = image.convert('L')
            
            # Check if image has changed
            image_hash = hash(image.tobytes())
            needs_update = (
                force_refresh or 
                image_hash != self.last_image_hash or
                self._should_force_refresh()
            )
            
            if not needs_update:
                self.logger.debug("Image unchanged, skipping update")
                return
            
            if self.simulation_mode:
                self._simulate_display(image)
            else:
                self._display_on_hardware(image, force_refresh)
            
            self.last_image_hash = image_hash
            self._check_memory_usage()
            
        except Exception as e:
            self.logger.error(f"Display update failed: {e}")
    
    def _simulate_display(self, image: Image.Image):
        """Simulate display by saving image to file."""
        simulation_path = 'current_display.png'
        image.save(simulation_path)
        self.logger.info(f"Display simulated - image saved to {simulation_path}")
    
    def _display_on_hardware(self, image: Image.Image, force_refresh: bool):
        """Display image on actual e-ink hardware."""
        if not self.display_device:
            raise RuntimeError("Display device not initialized")
        
        # Use our local display constants instead of IT8951 constants
        # Determine refresh mode
        if force_refresh or self._should_force_refresh():
            # Full refresh for better quality
            self.display_device.frame_buf.paste(image, (0, 0))
            self.display_device.draw_full(DisplayModes.GC16)
            self.last_full_refresh = time.time()
            self.logger.debug("Full display refresh")
        else:
            # Fast partial refresh
            self.display_device.frame_buf.paste(image, (0, 0))
            self.display_device.draw_partial(DisplayModes.DU)
            self.logger.debug("Partial display refresh")
    
    def _should_force_refresh(self) -> bool:
        """Check if a full refresh is needed based on time interval."""
        return (time.time() - self.last_full_refresh) > (self.force_refresh_interval * 60)
    
    def _check_memory_usage(self):
        """Monitor memory usage and trigger garbage collection if needed."""
        memory_percent = psutil.virtual_memory().percent
        threshold = int(os.getenv('MEMORY_THRESHOLD', '80'))
        
        if memory_percent > threshold:
            import gc
            gc.collect()
            self.logger.warning(f"High memory usage ({memory_percent}%), garbage collection triggered")
    
    def clear_display(self):
        """Clear the display to white."""
        white_image = Image.new('L', (self.width, self.height), 255)
        self.display_image(white_image, force_refresh=True)
    
    def get_display_info(self) -> dict:
        """Get display information."""
        return {
            'width': self.width,
            'height': self.height,
            'rotation': self.rotation,
            'simulation_mode': self.simulation_mode,
            'last_refresh': self.last_full_refresh
        }