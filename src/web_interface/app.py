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
    
    # Disable template caching for development
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
    
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
                'verses_today': getattr(app.verse_manager, 'statistics', {}).get('verses_today', 0),
                'system': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_percent': psutil.disk_usage('/').percent,
                    'cpu_temperature': _get_cpu_temperature(),
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
                'time_format': getattr(app.verse_manager, 'time_format', '12'),
                'background_index': app.image_generator.current_background_index,
                'available_backgrounds': app.image_generator.get_available_backgrounds(),
                'available_translations': ['kjv', 'web', 'asv', 'bbe', 'ylt'],
                'parallel_mode': getattr(app.verse_manager, 'parallel_mode', False),
                'secondary_translation': getattr(app.verse_manager, 'secondary_translation', 'web'),
                'available_fonts': app.image_generator.get_available_fonts(),
                'current_font': app.image_generator.get_current_font(),
                'font_sizes': app.image_generator.get_font_sizes(),
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
            
            # Update time format
            if 'time_format' in data:
                app.verse_manager.time_format = data['time_format']
                app.logger.info(f"Time format changed to: {data['time_format']}")
            
            # Update parallel mode
            if 'parallel_mode' in data:
                app.verse_manager.parallel_mode = data['parallel_mode']
                app.logger.info(f"Parallel mode: {data['parallel_mode']}")
            
            # Update secondary translation
            if 'secondary_translation' in data:
                app.verse_manager.secondary_translation = data['secondary_translation']
                app.logger.info(f"Secondary translation: {data['secondary_translation']}")
            
            # Update background
            if 'background_index' in data:
                app.image_generator.set_background(data['background_index'])
                app.logger.info(f"Background changed to index: {data['background_index']}")
            
            # Update font
            if 'font' in data:
                app.image_generator.set_font(data['font'])
                app.logger.info(f"Font changed to: {data['font']}")
            
            # Update font sizes
            if any(key in data for key in ['verse_size', 'reference_size']):
                app.image_generator.set_font_sizes(
                    verse_size=data.get('verse_size'),
                    reference_size=data.get('reference_size')
                )
                app.logger.info("Font sizes updated")
            
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
        """Get available backgrounds with previews and cycling settings."""
        try:
            backgrounds = app.image_generator.get_background_info()
            cycling_settings = app.image_generator.get_cycling_settings()
            backgrounds['cycling'] = cycling_settings
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
            
            # Add AI statistics if voice control is available
            if hasattr(app.service_manager, 'voice_control') and app.service_manager.voice_control:
                stats['ai_statistics'] = app.service_manager.voice_control.get_ai_statistics()
            else:
                # Provide empty AI statistics if voice control not available
                stats['ai_statistics'] = {
                    'total_tokens': 0,
                    'total_questions': 0,
                    'total_cost': 0.0,
                    'success_rate': 0,
                    'avg_response_time': 0,
                    'successful_requests': 0,
                    'failed_requests': 0,
                    'daily_usage': {}
                }
            
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
    
    @app.route('/api/background/cycle', methods=['POST'])
    def cycle_background():
        """Cycle to next background."""
        try:
            app.image_generator.cycle_background()
            
            # Update display if requested
            if request.get_json() and request.get_json().get('update_display', False):
                verse_data = app.verse_manager.get_current_verse()
                image = app.image_generator.create_verse_image(verse_data)
                app.display_manager.display_image(image, force_refresh=True)
            
            return jsonify({
                'success': True, 
                'message': 'Background cycled',
                'current_background': app.image_generator.get_current_background_info()
            })
        except Exception as e:
            app.logger.error(f"Background cycle error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/background/randomize', methods=['POST'])
    def randomize_background():
        """Randomize background."""
        try:
            app.image_generator.randomize_background()
            
            # Update display if requested
            if request.get_json() and request.get_json().get('update_display', False):
                verse_data = app.verse_manager.get_current_verse()
                image = app.image_generator.create_verse_image(verse_data)
                app.display_manager.display_image(image, force_refresh=True)
            
            return jsonify({
                'success': True, 
                'message': 'Background randomized',
                'current_background': app.image_generator.get_current_background_info()
            })
        except Exception as e:
            app.logger.error(f"Background randomize error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/background/cycling', methods=['POST'])
    def set_background_cycling():
        """Configure background cycling settings."""
        try:
            data = request.get_json()
            enabled = data.get('enabled', False)
            interval = data.get('interval_minutes', 30)
            
            app.image_generator.set_background_cycling(enabled, interval)
            
            return jsonify({
                'success': True,
                'message': 'Background cycling updated',
                'settings': app.image_generator.get_cycling_settings()
            })
        except Exception as e:
            app.logger.error(f"Background cycling error: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    @app.route('/api/preview', methods=['POST'])
    def preview_settings():
        """Preview settings without applying to display."""
        try:
            data = request.get_json()
            
            # Store original settings
            original_translation = app.verse_manager.translation
            original_display_mode = getattr(app.verse_manager, 'display_mode', 'time')
            original_parallel_mode = getattr(app.verse_manager, 'parallel_mode', False)
            original_secondary_translation = getattr(app.verse_manager, 'secondary_translation', 'web')
            original_background_index = app.image_generator.current_background_index
            original_font = app.image_generator.current_font_name
            original_font_sizes = app.image_generator.get_font_sizes()
            
            try:
                # Apply temporary changes
                if 'translation' in data:
                    app.verse_manager.translation = data['translation']
                
                if 'display_mode' in data:
                    app.verse_manager.display_mode = data['display_mode']
                
                if 'parallel_mode' in data:
                    app.verse_manager.parallel_mode = data['parallel_mode']
                
                if 'secondary_translation' in data:
                    app.verse_manager.secondary_translation = data['secondary_translation']
                
                if 'background_index' in data:
                    bg_index = data['background_index']
                    if 0 <= bg_index < len(app.image_generator.backgrounds):
                        app.image_generator.current_background_index = bg_index
                    else:
                        app.logger.warning(f"Invalid background index: {bg_index}")
                        app.image_generator.current_background_index = 0
                
                if 'font' in data:
                    app.image_generator.current_font_name = data['font']
                    app.image_generator._load_fonts_with_selection()
                
                if 'font_sizes' in data:
                    sizes = data['font_sizes']
                    app.image_generator.set_font_sizes(
                        verse_size=sizes.get('verse_size'),
                        reference_size=sizes.get('reference_size')
                    )
                
                # Generate preview
                verse_data = app.verse_manager.get_current_verse()
                image = app.image_generator.create_verse_image(verse_data)
                
                # Save preview image
                preview_path = Path('src/web_interface/static/preview.png')
                preview_path.parent.mkdir(exist_ok=True)
                image.save(preview_path)
                
                # Return success with metadata
                return jsonify({
                    'success': True, 
                    'preview_url': f'/static/preview.png?t={datetime.now().timestamp()}',
                    'timestamp': datetime.now().isoformat(),
                    'background_name': f"Background {app.image_generator.current_background_index + 1}",
                    'font_name': app.image_generator.current_font_name,
                    'verse_reference': verse_data.get('reference', 'Unknown')
                })
                
            finally:
                # Restore original settings
                app.verse_manager.translation = original_translation
                app.verse_manager.display_mode = original_display_mode
                app.verse_manager.parallel_mode = original_parallel_mode
                app.verse_manager.secondary_translation = original_secondary_translation
                app.image_generator.current_background_index = original_background_index
                app.image_generator.current_font_name = original_font
                app.image_generator.set_font_sizes(
                    verse_size=original_font_sizes['verse_size'],
                    reference_size=original_font_sizes['reference_size']
                )
            
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
            
            # Handle API key FIRST before enabling ChatGPT
            if 'chatgpt_api_key' in data:
                # Update the OpenAI API key
                api_key = data['chatgpt_api_key']
                if api_key and not api_key.startswith('•'):  # Not a masked value
                    voice_control.openai_api_key = api_key
                    # Re-initialize ChatGPT with the new key
                    voice_control._initialize_chatgpt()
                    app.logger.info("ChatGPT API key updated")
            
            # Now handle ChatGPT enabled/disabled AFTER API key is set
            if 'chatgpt_enabled' in data:
                voice_control.set_chatgpt_enabled(data['chatgpt_enabled'])
            
            if 'help_enabled' in data:
                voice_control.help_enabled = data['help_enabled']
            
            if 'voice_selection' in data:
                voice_control.voice_selection = data['voice_selection']
                # Apply voice selection if TTS engine is available
                if voice_control.tts_engine:
                    voices = voice_control.tts_engine.getProperty('voices')
                    if voices:
                        selection = data['voice_selection']
                        if selection == 'female':
                            female_voices = [v for v in voices if 'female' in v.name.lower() or 'woman' in v.name.lower()]
                            if female_voices:
                                voice_control.tts_engine.setProperty('voice', female_voices[0].id)
                        elif selection == 'male':
                            male_voices = [v for v in voices if 'male' in v.name.lower() or 'man' in v.name.lower()]
                            if male_voices:
                                voice_control.tts_engine.setProperty('voice', male_voices[0].id)
                        elif selection == 'calm':
                            # Look for voices with calm/soothing in name, fallback to first female
                            calm_voices = [v for v in voices if any(word in v.name.lower() for word in ['calm', 'sooth', 'gentle'])]
                            if calm_voices:
                                voice_control.tts_engine.setProperty('voice', calm_voices[0].id)
                            else:
                                female_voices = [v for v in voices if 'female' in v.name.lower()]
                                if female_voices:
                                    voice_control.tts_engine.setProperty('voice', female_voices[0].id)
                        elif selection == 'clear':
                            # Look for voices with clear/articulate in name
                            clear_voices = [v for v in voices if any(word in v.name.lower() for word in ['clear', 'articulate', 'crisp'])]
                            if clear_voices:
                                voice_control.tts_engine.setProperty('voice', clear_voices[0].id)
                            elif len(voices) > 1:
                                voice_control.tts_engine.setProperty('voice', voices[1].id)
                        # 'default' uses system default (no change needed)
            
            return jsonify({'success': True, 'message': 'Voice settings updated successfully'})
            
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
    
    def _get_cpu_temperature():
        """Get CPU temperature."""
        try:
            # Try Raspberry Pi thermal zone first
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_millidegrees = int(f.read().strip())
                temp_celsius = temp_millidegrees / 1000.0
                return round(temp_celsius, 1)
        except:
            try:
                # Try alternative thermal zones
                import glob
                thermal_files = glob.glob('/sys/class/thermal/thermal_zone*/temp')
                if thermal_files:
                    with open(thermal_files[0], 'r') as f:
                        temp_millidegrees = int(f.read().strip())
                        temp_celsius = temp_millidegrees / 1000.0
                        return round(temp_celsius, 1)
            except:
                pass
            
            # Simulation mode - return simulated temperature
            import random
            simulation_mode = os.getenv('SIMULATION_MODE', 'false').lower() == 'true'
            if simulation_mode:
                # Return a realistic simulated temperature
                return round(45.0 + random.uniform(-5, 10), 1)
            
            return None
    
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