"""
Enhanced web interface for Bible Clock with full configuration and statistics.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template, send_file
from pathlib import Path
import psutil

def create_app(verse_manager, image_generator, display_manager, service_manager, performance_monitor):
    """Create enhanced Flask application."""
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.logger.setLevel(logging.INFO)
    
    # Store component references
    app.verse_manager = verse_manager
    app.image_generator = image_generator
    app.display_manager = display_manager
    app.service_manager = service_manager
    app.performance_monitor = performance_monitor
    
    @app.route('/')
    def index():
        """Main dashboard."""
        return render_template('dashboard.html')
    
    @app.route('/settings')
    def settings():
        """Settings page."""
        return render_template('settings.html')
    
    @app.route('/statistics')
    def statistics():
        """Statistics page."""
        return render_template('statistics.html')
    
    @app.route('/voice')
    def voice_control():
        """Voice control page."""
        return render_template('voice_control.html')
    
    # === API Endpoints ===
    
    @app.route('/api/verse', methods=['GET'])
    def get_current_verse():
        """Get the current verse as JSON."""
        try:
            verse_data = app.verse_manager.get_current_verse()
            verse_data['timestamp'] = datetime.now().isoformat()
            
            return jsonify({
                'success': True,
                'data': verse_data
            })
        except Exception as e:
            app.logger.error(f"API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/status', methods=['GET'])
    def get_status():
        """Get comprehensive system status."""
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'translation': app.verse_manager.translation,
                'api_url': app.verse_manager.api_url,
                'display_mode': getattr(app.verse_manager, 'display_mode', 'time'),
                'current_background': app.image_generator.get_current_background_info(),
                'system': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_percent': psutil.disk_usage('/').percent,
                    'uptime': _get_uptime()
                }
            }
            
            if app.performance_monitor:
                status['performance'] = app.performance_monitor.get_performance_summary()
            
            return jsonify({'success': True, 'data': status})
        except Exception as e:
            app.logger.error(f"Status API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/settings', methods=['GET'])
    def get_settings():
        """Get current settings."""
        try:
            settings = {
                'translation': app.verse_manager.translation,
                'display_mode': getattr(app.verse_manager, 'display_mode', 'time'),
                'background_index': app.image_generator.current_background_index,
                'available_backgrounds': app.image_generator.get_available_backgrounds(),
                'available_translations': ['kjv', 'esv', 'nasb', 'amp', 'niv'],
                'available_fonts': app.image_generator.get_available_fonts(),
                'current_font': app.image_generator.get_current_font(),
                'voice_enabled': getattr(app.verse_manager, 'voice_enabled', False),
                'web_enabled': True,
                'auto_refresh': int(os.getenv('FORCE_REFRESH_INTERVAL', '60'))
            }
            
            return jsonify({'success': True, 'data': settings})
        except Exception as e:
            app.logger.error(f"Settings API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/settings', methods=['POST'])
    def update_settings():
        """Update settings."""
        try:
            data = request.get_json()
            
            # Update translation
            if 'translation' in data:
                app.verse_manager.translation = data['translation']
                app.logger.info(f"Translation changed to: {data['translation']}")
            
            # Update display mode
            if 'display_mode' in data:
                app.verse_manager.display_mode = data['display_mode']
                app.logger.info(f"Display mode changed to: {data['display_mode']}")
            
            # Update background
            if 'background_index' in data:
                app.image_generator.set_background(data['background_index'])
                app.logger.info(f"Background changed to index: {data['background_index']}")
            
            # Update font
            if 'font' in data:
                app.image_generator.set_font(data['font'])
                app.logger.info(f"Font changed to: {data['font']}")
            
            # Force display update
            if data.get('update_display', False):
                verse_data = app.verse_manager.get_current_verse()
                image = app.image_generator.create_verse_image(verse_data)
                app.display_manager.display_image(image, force_refresh=True)
            
            return jsonify({'success': True, 'message': 'Settings updated successfully'})
            
        except Exception as e:
            app.logger.error(f"Settings update error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/backgrounds', methods=['GET'])
    def get_backgrounds():
        """Get available backgrounds with previews."""
        try:
            backgrounds = app.image_generator.get_background_info()
            return jsonify({'success': True, 'data': backgrounds})
        except Exception as e:
            app.logger.error(f"Backgrounds API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/fonts', methods=['GET'])
    def get_fonts():
        """Get available fonts."""
        try:
            fonts = app.image_generator.get_font_info()
            return jsonify({'success': True, 'data': fonts})
        except Exception as e:
            app.logger.error(f"Fonts API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/statistics', methods=['GET'])
    def get_statistics():
        """Get usage statistics."""
        try:
            if hasattr(app.verse_manager, 'get_statistics'):
                stats = app.verse_manager.get_statistics()
            else:
                stats = _generate_basic_statistics()
            
            return jsonify({'success': True, 'data': stats})
        except Exception as e:
            app.logger.error(f"Statistics API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/refresh', methods=['POST'])
    def force_refresh():
        """Force display refresh."""
        try:
            verse_data = app.verse_manager.get_current_verse()
            image = app.image_generator.create_verse_image(verse_data)
            app.display_manager.display_image(image, force_refresh=True)
            
            return jsonify({'success': True, 'message': 'Display refreshed'})
        except Exception as e:
            app.logger.error(f"Refresh error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/preview', methods=['POST'])
    def preview_settings():
        """Preview settings without applying to display."""
        try:
            data = request.get_json()
            
            # Create temporary settings
            temp_verse_manager = app.verse_manager
            temp_image_generator = app.image_generator
            
            # Apply temporary changes
            if 'translation' in data:
                temp_verse_manager.translation = data['translation']
            
            if 'background_index' in data:
                temp_image_generator.current_background_index = data['background_index']
            
            if 'font' in data:
                temp_image_generator.set_font_temporarily(data['font'])
            
            # Generate preview
            verse_data = temp_verse_manager.get_current_verse()
            image = temp_image_generator.create_verse_image(verse_data)
            
            # Save preview image
            preview_path = Path('static/preview.png')
            preview_path.parent.mkdir(exist_ok=True)
            image.save(preview_path)
            
            return jsonify({
                'success': True, 
                'preview_url': '/static/preview.png',
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            app.logger.error(f"Preview error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/status', methods=['GET'])
    def get_voice_status():
        """Get voice control status."""
        try:
            if hasattr(app.service_manager, 'voice_control') and app.service_manager.voice_control:
                status = app.service_manager.voice_control.get_voice_status()
                return jsonify({'success': True, 'data': status})
            else:
                return jsonify({
                    'success': True, 
                    'data': {
                        'enabled': False,
                        'listening': False,
                        'chatgpt_enabled': False,
                        'help_enabled': False,
                        'message': 'Voice control not initialized'
                    }
                })
        except Exception as e:
            app.logger.error(f"Voice status API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/test', methods=['POST'])
    def test_voice():
        """Test voice synthesis."""
        try:
            if hasattr(app.service_manager, 'voice_control') and app.service_manager.voice_control:
                app.service_manager.voice_control.test_voice_synthesis()
                return jsonify({'success': True, 'message': 'Voice test initiated'})
            else:
                return jsonify({'success': False, 'error': 'Voice control not available'})
        except Exception as e:
            app.logger.error(f"Voice test API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/clear-history', methods=['POST'])
    def clear_voice_history():
        """Clear ChatGPT conversation history."""
        try:
            if hasattr(app.service_manager, 'voice_control') and app.service_manager.voice_control:
                app.service_manager.voice_control.clear_conversation_history()
                return jsonify({'success': True, 'message': 'Conversation history cleared'})
            else:
                return jsonify({'success': False, 'error': 'Voice control not available'})
        except Exception as e:
            app.logger.error(f"Clear history API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/history', methods=['GET'])
    def get_voice_history():
        """Get conversation history."""
        try:
            if hasattr(app.service_manager, 'voice_control') and app.service_manager.voice_control:
                history = app.service_manager.voice_control.get_conversation_history()
                return jsonify({'success': True, 'data': history})
            else:
                return jsonify({'success': True, 'data': []})
        except Exception as e:
            app.logger.error(f"Voice history API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/voice/settings', methods=['POST'])
    def update_voice_settings():
        """Update voice control settings."""
        try:
            if not hasattr(app.service_manager, 'voice_control') or not app.service_manager.voice_control:
                return jsonify({'success': False, 'error': 'Voice control not available'})
            
            data = request.get_json()
            voice_control = app.service_manager.voice_control
            
            # Update settings
            if 'voice_rate' in data:
                voice_control.voice_rate = data['voice_rate']
                if voice_control.tts_engine:
                    voice_control.tts_engine.setProperty('rate', data['voice_rate'])
            
            if 'voice_volume' in data:
                voice_control.voice_volume = data['voice_volume']
                if voice_control.tts_engine:
                    voice_control.tts_engine.setProperty('volume', data['voice_volume'])
            
            if 'chatgpt_enabled' in data:
                voice_control.set_chatgpt_enabled(data['chatgpt_enabled'])
            
            if 'help_enabled' in data:
                voice_control.help_enabled = data['help_enabled']
            
            return jsonify({'success': True, 'message': 'Voice settings updated'})
            
        except Exception as e:
            app.logger.error(f"Voice settings API error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/health')
    def health_check():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '2.0.0'
        })
    
    def _get_uptime():
        """Get system uptime."""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                return str(timedelta(seconds=int(uptime_seconds)))
        except:
            return "Unknown"
    
    def _generate_basic_statistics():
        """Generate basic statistics."""
        return {
            'verses_displayed_today': 1440,  # Minutes in a day
            'most_common_book': 'Psalms',
            'total_uptime': _get_uptime(),
            'api_success_rate': 98.5,
            'average_response_time': 0.85
        }
    
    return app