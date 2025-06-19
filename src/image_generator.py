"""
Generates images for Bible verses with backgrounds and typography.
"""

import os
import random
import logging
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Dict, Tuple, Optional, List
import textwrap
from datetime import datetime

class ImageGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.width = int(os.getenv('DISPLAY_WIDTH', '1872'))
        self.height = int(os.getenv('DISPLAY_HEIGHT', '1404'))
        
        # Enhanced font management
        self.available_fonts = {}
        self.current_font_name = 'default'
        
        # Font sizes (configurable)
        self.title_size = int(os.getenv('TITLE_FONT_SIZE', '48'))
        self.verse_size = int(os.getenv('VERSE_FONT_SIZE', '36'))
        self.reference_size = int(os.getenv('REFERENCE_FONT_SIZE', '32'))
        
        self._discover_fonts()
        
        # Load fonts
        self._load_fonts()
        
        # Load background images
        self._load_backgrounds()
        
        # Current background index for cycling
        self.current_background_index = 0
    
    def _load_fonts(self):
        """Load fonts for text rendering."""
        font_dir = Path('data/fonts')
        
        try:
            # Try to load DejaVu fonts with configurable sizes
            self.title_font = ImageFont.truetype(str(font_dir / 'DejaVuSans-Bold.ttf'), self.title_size)
            self.verse_font = ImageFont.truetype(str(font_dir / 'DejaVuSans.ttf'), self.verse_size)
            self.reference_font = ImageFont.truetype(str(font_dir / 'DejaVuSans-Bold.ttf'), self.reference_size)
            self.logger.info("Fonts loaded successfully")
        except Exception as e:
            self.logger.warning(f"Failed to load custom fonts: {e}")
            # Fallback to default font
            try:
                self.title_font = ImageFont.load_default()
                self.verse_font = ImageFont.load_default()
                self.reference_font = ImageFont.load_default()
            except:
                self.title_font = None
                self.verse_font = None
                self.reference_font = None
    
    def _discover_fonts(self):
        """Discover available fonts."""
        font_dir = Path('data/fonts')
        self.available_fonts = {'default': None}
        
        if font_dir.exists():
            for font_file in font_dir.glob('*.ttf'):
                font_name = font_file.stem
                try:
                    # Test loading the font
                    test_font = ImageFont.truetype(str(font_file), 24)
                    self.available_fonts[font_name] = str(font_file)
                    self.logger.debug(f"Found font: {font_name}")
                except Exception as e:
                    self.logger.warning(f"Could not load font {font_file}: {e}")
    
    def _load_backgrounds(self):
        """Load background images."""
        self.backgrounds = []
        background_dir = Path('images')
        
        background_files = [
            'subtle_cross.png',
            'minimalist_frame.png',
            'parchment.png',
            'stained_glass.png',
            'nature_border.png',
            'geometric.png',
            'watercolor.png',
            'classic_scroll.png'
        ]
        
        for bg_file in background_files:
            bg_path = background_dir / bg_file
            if bg_path.exists():
                try:
                    bg_image = Image.open(bg_path)
                    # Resize to display dimensions
                    bg_image = bg_image.resize((self.width, self.height), Image.Resampling.LANCZOS)
                    # Convert to grayscale for e-ink
                    bg_image = bg_image.convert('L')
                    self.backgrounds.append(bg_image)
                    self.logger.debug(f"Loaded background: {bg_file}")
                except Exception as e:
                    self.logger.warning(f"Failed to load background {bg_file}: {e}")
        
        if not self.backgrounds:
            # Create a simple default background
            self.backgrounds.append(self._create_default_background())
            self.logger.info("Using default background")
        else:
            self.logger.info(f"Loaded {len(self.backgrounds)} background images")
    
    def _create_default_background(self) -> Image.Image:
        """Create a simple default background."""
        bg = Image.new('L', (self.width, self.height), 255)  # White background
        draw = ImageDraw.Draw(bg)
        
        # Add a simple border
        border_width = 20
        draw.rectangle([
            border_width, border_width,
            self.width - border_width, self.height - border_width
        ], outline=128, width=3)
        
        return bg
    
    def create_verse_image(self, verse_data: Dict) -> Image.Image:
        """Create an image for a Bible verse."""
        # Get current background
        background = self.backgrounds[self.current_background_index].copy()
        
        # Create overlay for text
        overlay = Image.new('RGBA', (self.width, self.height), (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)
        
        # Define text areas
        margin = 80
        content_width = self.width - (2 * margin)
        
        # Check for different verse types
        is_summary = verse_data.get('is_summary', False)
        is_date_event = verse_data.get('is_date_event', False)
        is_parallel = verse_data.get('parallel_mode', False)
        
        if is_date_event:
            self._draw_date_event(draw, verse_data, margin, content_width)
        elif is_summary:
            self._draw_book_summary(draw, verse_data, margin, content_width)
        elif is_parallel:
            self._draw_parallel_verse(draw, verse_data, margin, content_width)
        else:
            self._draw_verse(draw, verse_data, margin, content_width)
        
        # Composite overlay onto background
        # Convert overlay to grayscale for e-ink
        overlay_gray = overlay.convert('L')
        
        # Create a mask for blending
        mask = Image.new('L', (self.width, self.height), 128)
        result = Image.composite(overlay_gray, background, mask)
        
        return result
    
    def _draw_verse(self, draw: ImageDraw.Draw, verse_data: Dict, margin: int, content_width: int):
        """Draw a regular Bible verse."""
        y_position = margin
        
        # Draw reference at top
        reference = verse_data['reference']
        if self.reference_font:
            ref_bbox = draw.textbbox((0, 0), reference, font=self.reference_font)
            ref_width = ref_bbox[2] - ref_bbox[0]
            ref_x = (self.width - ref_width) // 2
            draw.text((ref_x, y_position), reference, fill=0, font=self.reference_font)
            y_position += ref_bbox[3] - ref_bbox[1] + 40
        
        # Draw verse text (wrapped)
        verse_text = verse_data['text']
        wrapped_text = self._wrap_text(verse_text, content_width, self.verse_font)
        
        for line in wrapped_text:
            if self.verse_font:
                line_bbox = draw.textbbox((0, 0), line, font=self.verse_font)
                line_width = line_bbox[2] - line_bbox[0]
                line_x = (self.width - line_width) // 2
                draw.text((line_x, y_position), line, fill=0, font=self.verse_font)
                y_position += line_bbox[3] - line_bbox[1] + 20
        
        # Add decorative elements
        self._add_decorative_elements(draw, y_position)
    
    def _draw_book_summary(self, draw: ImageDraw.Draw, verse_data: Dict, margin: int, content_width: int):
        """Draw a book summary."""
        y_position = margin
        
        # Draw title
        title = f"Book of {verse_data['book']}"
        if self.title_font:
            title_bbox = draw.textbbox((0, 0), title, font=self.title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (self.width - title_width) // 2
            draw.text((title_x, y_position), title, fill=0, font=self.title_font)
            y_position += title_bbox[3] - title_bbox[1] + 60
        
        # Draw summary text (wrapped)
        summary_text = verse_data['text']
        wrapped_text = self._wrap_text(summary_text, content_width, self.verse_font)
        
        for line in wrapped_text:
            if self.verse_font:
                line_bbox = draw.textbbox((0, 0), line, font=self.verse_font)
                line_width = line_bbox[2] - line_bbox[0]
                line_x = (self.width - line_width) // 2
                draw.text((line_x, y_position), line, fill=0, font=self.verse_font)
                y_position += line_bbox[3] - line_bbox[1] + 25
    
    def _wrap_text(self, text: str, max_width: int, font: Optional[ImageFont.ImageFont]) -> list:
        """Wrap text to fit within specified width."""
        if not font:
            # Simple character-based wrapping if no font available
            chars_per_line = max_width // 10  # Rough estimate
            return textwrap.wrap(text, width=chars_per_line)
        
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            bbox = font.getbbox(test_line)
            line_width = bbox[2] - bbox[0]
            
            if line_width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Word is too long, break it
                    lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
    
    def _add_decorative_elements(self, draw: ImageDraw.Draw, y_position: int):
        """Add decorative elements to the image."""
        # Add a simple decorative line
        if y_position < self.height - 200:
            line_y = y_position + 40
            line_start = self.width // 4
            line_end = 3 * self.width // 4
            draw.line([(line_start, line_y), (line_end, line_y)], fill=128, width=2)
    
    def create_splash_image(self, message: str) -> Image.Image:
        """Create splash screen image."""
        # Use a simple background for splash
        image = Image.new('L', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        
        # Add border
        border_width = 40
        draw.rectangle([
            border_width, border_width,
            self.width - border_width, self.height - border_width
        ], outline=0, width=5)
        
        # Draw message
        margin = 100
        content_width = self.width - (2 * margin)
        
        wrapped_text = self._wrap_text(message, content_width, self.title_font)
        y_position = (self.height - len(wrapped_text) * 60) // 2
        
        for line in wrapped_text:
            if self.title_font:
                line_bbox = draw.textbbox((0, 0), line, font=self.title_font)
                line_width = line_bbox[2] - line_bbox[0]
                line_x = (self.width - line_width) // 2
                draw.text((line_x, y_position), line, fill=0, font=self.title_font)
                y_position += 60
        
        return image
    
    def cycle_background(self):
        """Cycle to the next background image."""
        self.current_background_index = (self.current_background_index + 1) % len(self.backgrounds)
        self.logger.info(f"Switched to background {self.current_background_index + 1}/{len(self.backgrounds)}")
    
    def get_current_background_info(self) -> Dict:
        """Get information about current background."""
        return {
            'current_index': self.current_background_index,
            'total_backgrounds': len(self.backgrounds),
            'current_name': f"Background {self.current_background_index + 1}"
        }
    
    def get_available_fonts(self) -> List[str]:
        """Get list of available font names."""
        return list(self.available_fonts.keys())
    
    def get_current_font(self) -> str:
        """Get current font name."""
        return self.current_font_name
    
    def set_font(self, font_name: str):
        """Set current font."""
        if font_name in self.available_fonts:
            self.current_font_name = font_name
            self._load_fonts()  # Reload fonts with new selection
            self.logger.info(f"Font changed to: {font_name}")
        else:
            raise ValueError(f"Font not available: {font_name}")
    
    def set_font_temporarily(self, font_name: str):
        """Temporarily set font for preview without persisting."""
        if font_name in self.available_fonts:
            old_font = self.current_font_name
            self.current_font_name = font_name
            self._load_fonts()
            return old_font
        return None
    
    def get_available_backgrounds(self) -> List[Dict]:
        """Get available backgrounds with metadata."""
        bg_info = []
        for i, bg in enumerate(self.backgrounds):
            bg_info.append({
                'index': i,
                'name': f"Background {i + 1}",
                'current': i == self.current_background_index
            })
        return bg_info
    
    def set_background(self, index: int):
        """Set background by index."""
        if 0 <= index < len(self.backgrounds):
            self.current_background_index = index
            self.logger.info(f"Background changed to index: {index}")
        else:
            raise ValueError(f"Background index out of range: {index}")
    
    def get_background_info(self) -> Dict:
        """Get detailed background information."""
        return {
            'current_index': self.current_background_index,
            'total_count': len(self.backgrounds),
            'backgrounds': self.get_available_backgrounds()
        }
    
    def get_current_background_info(self) -> Dict:
        """Get current background information."""
        return {
            'index': self.current_background_index,
            'name': f"Background {self.current_background_index + 1}",
            'total': len(self.backgrounds)
        }
    
    def get_available_fonts(self) -> List[Dict]:
        """Get available fonts with metadata."""
        return [
            {
                'name': name,
                'display_name': name.replace('_', ' ').title() if name != 'default' else 'Default',
                'path': path,
                'current': name == self.current_font_name
            }
            for name, path in self.available_fonts.items()
        ]
    
    def get_current_font(self) -> str:
        """Get current font name."""
        return self.current_font_name
    
    def set_font_sizes(self, title_size: int = None, verse_size: int = None, reference_size: int = None):
        """Set font sizes."""
        if title_size is not None:
            self.title_size = max(12, min(72, title_size))  # Clamp between 12-72
        if verse_size is not None:
            self.verse_size = max(12, min(60, verse_size))  # Clamp between 12-60
        if reference_size is not None:
            self.reference_size = max(12, min(48, reference_size))  # Clamp between 12-48
        
        # Reload fonts with new sizes
        self._load_fonts()
        self.logger.info(f"Font sizes updated - Title: {self.title_size}, Verse: {self.verse_size}, Reference: {self.reference_size}")
    
    def get_font_sizes(self) -> Dict[str, int]:
        """Get current font sizes."""
        return {
            'title_size': self.title_size,
            'verse_size': self.verse_size,
            'reference_size': self.reference_size
        }
    
    def cycle_background(self):
        """Cycle to next background."""
        self.current_background_index = (self.current_background_index + 1) % len(self.backgrounds)
        self.logger.info(f"Background cycled to index: {self.current_background_index}")
    
    def randomize_background(self):
        """Set random background."""
        if len(self.backgrounds) > 1:
            # Ensure we don't select the same background
            old_index = self.current_background_index
            while self.current_background_index == old_index:
                self.current_background_index = random.randint(0, len(self.backgrounds) - 1)
            self.logger.info(f"Background randomized to index: {self.current_background_index}")
    
    def get_font_info(self) -> Dict:
        """Get detailed font information."""
        return {
            'current_font': self.current_font_name,
            'available_fonts': [
                {
                    'name': name,
                    'path': path,
                    'current': name == self.current_font_name
                }
                for name, path in self.available_fonts.items()
            ]
        }
    
    def _draw_date_event(self, draw: ImageDraw.Draw, verse_data: Dict, margin: int, content_width: int):
        """Draw a date-based biblical event."""
        y_position = margin
        
        # Draw event name at top
        event_name = verse_data.get('event_name', 'Biblical Event')
        if self.title_font:
            title_bbox = draw.textbbox((0, 0), event_name, font=self.title_font)
            title_width = title_bbox[2] - title_bbox[0]
            title_x = (self.width - title_width) // 2
            draw.text((title_x, y_position), event_name, fill=0, font=self.title_font)
            y_position += title_bbox[3] - title_bbox[1] + 40
        
        # Draw date match type indicator
        match_type = verse_data.get('date_match', 'exact')
        match_text = {
            'exact': f"Today - {datetime.now().strftime('%B %d')}",
            'week': f"This Week - {datetime.now().strftime('%B %d')}",
            'month': f"This Month - {datetime.now().strftime('%B')}",
            'season': f"This Season - {datetime.now().strftime('%B')}",
            'fallback': f"Daily Blessing - {datetime.now().strftime('%B %d')}"
        }.get(match_type, "Today")
        
        if self.reference_font:
            ref_bbox = draw.textbbox((0, 0), match_text, font=self.reference_font)
            ref_width = ref_bbox[2] - ref_bbox[0]
            ref_x = (self.width - ref_width) // 2
            draw.text((ref_x, y_position), match_text, fill=64, font=self.reference_font)
            y_position += ref_bbox[3] - ref_bbox[1] + 30
        
        # Draw reference
        reference = verse_data['reference']
        if self.reference_font:
            ref_bbox = draw.textbbox((0, 0), reference, font=self.reference_font)
            ref_width = ref_bbox[2] - ref_bbox[0]
            ref_x = (self.width - ref_width) // 2
            draw.text((ref_x, y_position), reference, fill=0, font=self.reference_font)
            y_position += ref_bbox[3] - ref_bbox[1] + 40
        
        # Draw verse text
        verse_text = verse_data['text']
        wrapped_text = self._wrap_text(verse_text, content_width, self.verse_font)
        
        for line in wrapped_text:
            if self.verse_font:
                line_bbox = draw.textbbox((0, 0), line, font=self.verse_font)
                line_width = line_bbox[2] - line_bbox[0]
                line_x = (self.width - line_width) // 2
                draw.text((line_x, y_position), line, fill=0, font=self.verse_font)
                y_position += line_bbox[3] - line_bbox[1] + 20
        
        # Draw event description if space allows
        if y_position < self.height - 200:
            y_position += 40
            description = verse_data.get('event_description', '')
            if description:
                wrapped_desc = self._wrap_text(description, content_width, self.reference_font)
                for line in wrapped_desc[:2]:  # Max 2 lines for description
                    if self.reference_font:
                        line_bbox = draw.textbbox((0, 0), line, font=self.reference_font)
                        line_width = line_bbox[2] - line_bbox[0]
                        line_x = (self.width - line_width) // 2
                        draw.text((line_x, y_position), line, fill=96, font=self.reference_font)
                        y_position += line_bbox[3] - line_bbox[1] + 15
    
    def _draw_parallel_verse(self, draw: ImageDraw.Draw, verse_data: Dict, margin: int, content_width: int):
        """Draw verse with parallel translations side by side."""
        y_position = margin
        
        # Draw reference at top (centered)
        reference = verse_data['reference']
        if self.reference_font:
            ref_bbox = draw.textbbox((0, 0), reference, font=self.reference_font)
            ref_width = ref_bbox[2] - ref_bbox[0]
            ref_x = (self.width - ref_width) // 2
            draw.text((ref_x, y_position), reference, fill=0, font=self.reference_font)
            y_position += ref_bbox[3] - ref_bbox[1] + 30
        
        # Draw translation labels
        primary_label = verse_data.get('primary_translation', 'KJV')
        secondary_label = verse_data.get('secondary_translation', 'AMP')
        
        if self.reference_font:
            # Left label
            left_bbox = draw.textbbox((0, 0), primary_label, font=self.reference_font)
            left_x = margin + (content_width // 4) - ((left_bbox[2] - left_bbox[0]) // 2)
            draw.text((left_x, y_position), primary_label, fill=64, font=self.reference_font)
            
            # Right label
            right_bbox = draw.textbbox((0, 0), secondary_label, font=self.reference_font)
            right_x = margin + (3 * content_width // 4) - ((right_bbox[2] - right_bbox[0]) // 2)
            draw.text((right_x, y_position), secondary_label, fill=64, font=self.reference_font)
            
            y_position += left_bbox[3] - left_bbox[1] + 30
        
        # Split content into two columns
        column_width = (content_width - 40) // 2  # 40px gap between columns
        left_margin = margin
        right_margin = margin + column_width + 40
        
        # Draw primary translation (left)
        primary_text = verse_data['text']
        wrapped_primary = self._wrap_text(primary_text, column_width, self.verse_font)
        
        for line in wrapped_primary:
            if self.verse_font:
                line_bbox = draw.textbbox((0, 0), line, font=self.verse_font)
                draw.text((left_margin, y_position), line, fill=0, font=self.verse_font)
                y_position += line_bbox[3] - line_bbox[1] + 15
        
        # Reset y_position for secondary translation
        y_position = margin
        if self.reference_font:
            ref_bbox = draw.textbbox((0, 0), reference, font=self.reference_font)
            y_position += ref_bbox[3] - ref_bbox[1] + 30
            left_bbox = draw.textbbox((0, 0), primary_label, font=self.reference_font)
            y_position += left_bbox[3] - left_bbox[1] + 30
        
        # Draw secondary translation (right)
        secondary_text = verse_data.get('secondary_text', 'Translation not available')
        wrapped_secondary = self._wrap_text(secondary_text, column_width, self.verse_font)
        
        for line in wrapped_secondary:
            if self.verse_font:
                line_bbox = draw.textbbox((0, 0), line, font=self.verse_font)
                draw.text((right_margin, y_position), line, fill=0, font=self.verse_font)
                y_position += line_bbox[3] - line_bbox[1] + 15
        
        # Add a vertical separator line
        separator_x = margin + column_width + 20
        separator_start_y = margin + 80
        separator_end_y = y_position - 20
        draw.line([(separator_x, separator_start_y), (separator_x, separator_end_y)], fill=128, width=1)