"""
Manages Bible verse retrieval and scheduling.
"""

import json
import random
import requests
import logging
from datetime import datetime, time, date
from pathlib import Path
from typing import Dict, List, Optional
import os
import calendar

class VerseManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_url = os.getenv('BIBLE_API_URL', 'https://bible-api.com')
        self.translation = os.getenv('DEFAULT_TRANSLATION', 'kjv')
        self.timeout = int(os.getenv('REQUEST_TIMEOUT', '10'))
        
        # Enhanced features
        self.display_mode = 'time'  # 'time', 'date', 'random'
        self.statistics = {
            'verses_displayed': 0,
            'verses_today': 0,
            'books_accessed': set(),
            'translation_usage': {},
            'mode_usage': {'time': 0, 'date': 0, 'random': 0}
        }
        self.start_time = datetime.now()
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Load local data
        self._load_fallback_verses()
        self._load_book_summaries()
        self._load_kjv_bible()
        self._load_biblical_calendar()
        
        # All available Bible books (will be populated from local data)
        self.available_books = []
        self._populate_available_books()
    
    def _load_fallback_verses(self):
        """Load fallback verses from JSON file."""
        try:
            fallback_path = Path('data/fallback_verses.json')
            with open(fallback_path, 'r') as f:
                self.fallback_verses = json.load(f)
            self.logger.info(f"Loaded {len(self.fallback_verses)} fallback verses")
        except Exception as e:
            self.logger.error(f"Failed to load fallback verses: {e}")
            self.fallback_verses = self._get_default_fallback_verses()
    
    def _load_book_summaries(self):
        """Load book summaries from JSON file."""
        try:
            summaries_path = Path('data/book_summaries.json')
            with open(summaries_path, 'r') as f:
                self.book_summaries = json.load(f)
            self.logger.info(f"Loaded {len(self.book_summaries)} book summaries")
        except Exception as e:
            self.logger.error(f"Failed to load book summaries: {e}")
            self.book_summaries = {}
    
    def _load_kjv_bible(self):
        """Load complete KJV Bible for offline use."""
        try:
            kjv_path = Path('data/translations/bible_kjv.json')
            with open(kjv_path, 'r') as f:
                self.kjv_bible = json.load(f)
            self.logger.info("Loaded complete KJV Bible")
        except Exception as e:
            self.logger.error(f"Failed to load KJV Bible: {e}")
            self.kjv_bible = {}
    
    def _load_biblical_calendar(self):
        """Load biblical events calendar."""
        try:
            calendar_path = Path('data/biblical_calendar.json')
            if calendar_path.exists():
                with open(calendar_path, 'r') as f:
                    self.biblical_calendar = json.load(f)
            else:
                self.biblical_calendar = self._get_default_biblical_calendar()
            self.logger.info(f"Loaded biblical calendar with {len(self.biblical_calendar)} entries")
        except Exception as e:
            self.logger.error(f"Failed to load biblical calendar: {e}")
            self.biblical_calendar = self._get_default_biblical_calendar()
    
    def _populate_available_books(self):
        """Populate the list of available books from local KJV data."""
        if self.kjv_bible:
            self.available_books = list(self.kjv_bible.keys())
        else:
            # Fallback list of common Bible books
            self.available_books = [
                'Genesis', 'Exodus', 'Leviticus', 'Numbers', 'Deuteronomy',
                'Joshua', 'Judges', 'Ruth', '1 Samuel', '2 Samuel',
                '1 Kings', '2 Kings', '1 Chronicles', '2 Chronicles',
                'Ezra', 'Nehemiah', 'Esther', 'Job', 'Psalms', 'Proverbs',
                'Ecclesiastes', 'Song of Solomon', 'Isaiah', 'Jeremiah',
                'Lamentations', 'Ezekiel', 'Daniel', 'Hosea', 'Joel',
                'Amos', 'Obadiah', 'Jonah', 'Micah', 'Nahum', 'Habakkuk',
                'Zephaniah', 'Haggai', 'Zechariah', 'Malachi',
                'Matthew', 'Mark', 'Luke', 'John', 'Acts', 'Romans',
                '1 Corinthians', '2 Corinthians', 'Galatians', 'Ephesians',
                'Philippians', 'Colossians', '1 Thessalonians', '2 Thessalonians',
                '1 Timothy', '2 Timothy', 'Titus', 'Philemon', 'Hebrews',
                'James', '1 Peter', '2 Peter', '1 John', '2 John', '3 John',
                'Jude', 'Revelation'
            ]
        
        self.logger.info(f"Available books: {len(self.available_books)}")
    
    def _get_books_with_chapter(self, chapter_num: int) -> list:
        """Get list of books that have the specified chapter number."""
        books_with_chapter = []
        
        for book in self.available_books:
            if self.kjv_bible and book in self.kjv_bible:
                # Check local KJV data
                book_data = self.kjv_bible[book]
                if str(chapter_num) in book_data:
                    books_with_chapter.append(book)
            else:
                # For books not in local data, make educated guesses
                # This is a fallback when KJV data isn't available
                if self._book_likely_has_chapter(book, chapter_num):
                    books_with_chapter.append(book)
        
        return books_with_chapter
    
    def _book_likely_has_chapter(self, book: str, chapter_num: int) -> bool:
        """Estimate if a book likely has the given chapter (fallback method)."""
        # Rough estimates for when KJV data isn't available
        book_chapter_estimates = {
            'Psalms': 150, 'Isaiah': 66, 'Jeremiah': 52, 'Genesis': 50,
            'Ezekiel': 48, 'Job': 42, 'Exodus': 40, 'Numbers': 36,
            'Deuteronomy': 34, '1 Chronicles': 29, '2 Chronicles': 36,
            'Matthew': 28, 'Acts': 28, 'Luke': 24, '1 Kings': 22,
            '2 Kings': 25, 'Leviticus': 27, 'Joshua': 24, 'Judges': 21,
            'John': 21, '1 Samuel': 31, '2 Samuel': 24, 'Romans': 16,
            'Mark': 16, '1 Corinthians': 16, '2 Corinthians': 13,
            'Hebrews': 13, 'Revelation': 22, 'Proverbs': 31
        }
        
        estimated_chapters = book_chapter_estimates.get(book, 10)  # Default to 10
        return chapter_num <= estimated_chapters
    
    def _get_default_fallback_verses(self) -> List[Dict]:
        """Return default fallback verses if file loading fails."""
        return [
            {
                "reference": "John 3:16",
                "text": "For God so loved the world, that he gave his only begotten Son, that whosoever believeth in him should not perish, but have everlasting life.",
                "book": "John",
                "chapter": 3,
                "verse": 16
            },
            {
                "reference": "Psalm 23:1",
                "text": "The LORD is my shepherd; I shall not want.",
                "book": "Psalms",
                "chapter": 23,
                "verse": 1
            },
            {
                "reference": "Romans 8:28",
                "text": "And we know that all things work together for good to them that love God, to them who are the called according to his purpose.",
                "book": "Romans",
                "chapter": 8,
                "verse": 28
            }
        ]
    
    def get_current_verse(self) -> Dict:
        """Get verse based on current display mode."""
        # Check if we need to reset daily counter
        now = datetime.now()
        if now.date() > self.daily_reset_time.date():
            self.statistics['verses_today'] = 0
            self.daily_reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        self.statistics['verses_displayed'] += 1
        self.statistics['verses_today'] += 1
        
        if self.display_mode == 'date':
            verse_data = self._get_date_based_verse()
        elif self.display_mode == 'random':
            verse_data = self._get_random_verse()
        else:  # time mode
            verse_data = self._get_time_based_verse()
        
        # Update statistics
        self.statistics['mode_usage'][self.display_mode] += 1
        if verse_data.get('book'):
            self.statistics['books_accessed'].add(verse_data['book'])
        
        translation = getattr(self, 'translation', 'kjv')
        self.statistics['translation_usage'][translation] = self.statistics['translation_usage'].get(translation, 0) + 1
        
        return verse_data
    
    def _get_time_based_verse(self) -> Dict:
        """Original time-based verse logic."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        
        if minute == 0:
            return self._get_random_book_summary()
        
        chapter = hour if hour > 0 else 24
        verse = minute
        
        verse_data = self._get_verse_from_api(chapter, verse)
        if not verse_data:
            verse_data = self._get_verse_from_local_data(chapter, verse)
        if not verse_data:
            verse_data = random.choice(self.fallback_verses)
        
        return verse_data
    
    def _get_date_based_verse(self) -> Dict:
        """Get verse based on today's date and biblical events."""
        today = date.today()
        
        # Try exact date match (MM-DD)
        date_key = f"{today.month}-{today.day}"
        if date_key in self.biblical_calendar:
            event = self.biblical_calendar[date_key]
            return {
                'reference': event['reference'],
                'text': event['text'],
                'book': event['reference'].split()[0],
                'chapter': 0,
                'verse': 0,
                'is_date_event': True,
                'event_name': event['event'],
                'event_description': event['description'],
                'date_match': 'exact'
            }
        
        # Try week match (same week of year)
        week_events = self._get_week_events(today)
        if week_events:
            event = random.choice(week_events)
            return {
                'reference': event['reference'],
                'text': event['text'],
                'book': event['reference'].split()[0],
                'chapter': 0,
                'verse': 0,
                'is_date_event': True,
                'event_name': event['event'],
                'event_description': event['description'],
                'date_match': 'week'
            }
        
        # Try month match
        month_events = self._get_month_events(today.month)
        if month_events:
            event = random.choice(month_events)
            return {
                'reference': event['reference'],
                'text': event['text'],
                'book': event['reference'].split()[0],
                'chapter': 0,
                'verse': 0,
                'is_date_event': True,
                'event_name': event['event'],
                'event_description': event['description'],
                'date_match': 'month'
            }
        
        # Try season match
        season_event = self._get_season_event(today)
        if season_event:
            return {
                'reference': season_event['reference'],
                'text': season_event['text'],
                'book': season_event['reference'].split()[0],
                'chapter': 0,
                'verse': 0,
                'is_date_event': True,
                'event_name': season_event['event'],
                'event_description': season_event['description'],
                'date_match': 'season'
            }
        
        # Fallback to random verse with date context
        fallback = random.choice(self.fallback_verses)
        fallback['is_date_event'] = True
        fallback['event_name'] = f"Daily Blessing for {today.strftime('%B %d')}"
        fallback['event_description'] = "God's word for today"
        fallback['date_match'] = 'fallback'
        
        return fallback
    
    def _get_random_verse(self) -> Dict:
        """Get a completely random verse."""
        return random.choice(self.fallback_verses)
    
    def _get_random_book_summary(self) -> Dict:
        """Get a random book summary."""
        if self.book_summaries:
            book = random.choice(list(self.book_summaries.keys()))
            summary = self.book_summaries[book]
        else:
            # Fallback if no summaries available
            book = random.choice(self.available_books)
            summary = {
                'title': book,
                'summary': f'{book} is a book of the Bible containing wisdom and spiritual guidance.'
            }
        
        return {
            'reference': f'{book} - Book Summary',
            'text': summary['summary'],
            'book': book,
            'chapter': 0,
            'verse': 0,
            'is_summary': True
        }
    
    def _get_verse_from_api(self, chapter: int, verse: int) -> Optional[Dict]:
        """Try to get verse from online API."""
        if not self.api_url:
            return None
        
        try:
            # Get books that have the required chapter
            books_with_chapter = self._get_books_with_chapter(chapter)
            
            if not books_with_chapter:
                self.logger.warning(f"No books found with chapter {chapter}")
                return None
            
            # Randomly select a book from those that have the chapter
            book = random.choice(books_with_chapter)
            
            url = f"{self.api_url}/{book} {chapter}:{verse}"
            if self.translation != 'kjv':
                url += f"?translation={self.translation}"
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            
            # Check if the API returned valid data
            verse_text = data.get('text', '').strip()
            if not verse_text:
                self.logger.warning(f"Empty verse returned from API for {book} {chapter}:{verse}")
                return None
            
            return {
                'reference': data.get('reference', f"{book} {chapter}:{verse}"),
                'text': verse_text,
                'book': book,
                'chapter': chapter,
                'verse': verse
            }
            
        except Exception as e:
            self.logger.warning(f"API request failed: {e}")
            return None
    
    def _get_verse_from_local_data(self, chapter: int, verse: int) -> Optional[Dict]:
        """Get verse from local KJV data."""
        try:
            # Get books that have the required chapter
            books_with_chapter = self._get_books_with_chapter(chapter)
            
            if not books_with_chapter:
                self.logger.warning(f"No books found with chapter {chapter}")
                return None
            
            # Try each book until we find one with the verse
            random.shuffle(books_with_chapter)  # Randomize the order
            
            for book in books_with_chapter:
                book_data = self.kjv_bible.get(book, {})
                chapter_data = book_data.get(str(chapter), {})
                verse_text = chapter_data.get(str(verse))
                
                if verse_text:
                    return {
                        'reference': f"{book} {chapter}:{verse}",
                        'text': verse_text,
                        'book': book,
                        'chapter': chapter,
                        'verse': verse
                    }
            
            # If exact verse not found, try to find a verse in the chapter
            for book in books_with_chapter:
                book_data = self.kjv_bible.get(book, {})
                chapter_data = book_data.get(str(chapter), {})
                
                if chapter_data:
                    # Get the highest verse number available in this chapter
                    available_verses = [int(v) for v in chapter_data.keys() if v.isdigit()]
                    if available_verses:
                        # Use the verse number closest to what we want, but not exceeding it
                        suitable_verses = [v for v in available_verses if v <= verse]
                        if suitable_verses:
                            actual_verse = max(suitable_verses)
                        else:
                            actual_verse = min(available_verses)
                        
                        verse_text = chapter_data[str(actual_verse)]
                        
                        return {
                            'reference': f"{book} {chapter}:{actual_verse}",
                            'text': verse_text,
                            'book': book,
                            'chapter': chapter,
                            'verse': actual_verse
                        }
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Local data lookup failed: {e}")
            return None
    
    def _get_week_events(self, target_date: date) -> List[Dict]:
        """Get events from the same week of the year."""
        target_week = target_date.isocalendar()[1]
        week_events = []
        
        for date_key, event in self.biblical_calendar.items():
            try:
                month, day = map(int, date_key.split('-'))
                event_date = date(target_date.year, month, day)
                event_week = event_date.isocalendar()[1]
                
                if abs(event_week - target_week) <= 1:  # Same or adjacent week
                    week_events.append(event)
            except (ValueError, TypeError):
                continue
        
        return week_events
    
    def _get_month_events(self, target_month: int) -> List[Dict]:
        """Get events from the same month."""
        month_events = []
        
        for date_key, event in self.biblical_calendar.items():
            try:
                month, day = map(int, date_key.split('-'))
                if month == target_month:
                    month_events.append(event)
            except (ValueError, TypeError):
                continue
        
        return month_events
    
    def _get_season_event(self, target_date: date) -> Optional[Dict]:
        """Get event based on current season."""
        # Determine season
        month = target_date.month
        day = target_date.day
        
        if (month == 12 and day >= 21) or month in [1, 2] or (month == 3 and day < 20):
            season = "winter"
            season_key = "12-21"  # Winter solstice
        elif (month == 3 and day >= 20) or month in [4, 5] or (month == 6 and day < 21):
            season = "spring"
            season_key = "3-21"  # Spring equinox
        elif (month == 6 and day >= 21) or month in [7, 8] or (month == 9 and day < 22):
            season = "summer"
            season_key = "6-21"  # Summer solstice
        else:
            season = "autumn"
            season_key = "9-22"  # Autumn equinox
        
        return self.biblical_calendar.get(season_key)
    
    def _get_default_biblical_calendar(self):
        """Default biblical calendar events."""
        return {
            "1-1": {
                "event": "New Year - God's Covenant Renewal",
                "reference": "Lamentations 3:22-23",
                "text": "It is of the LORD'S mercies that we are not consumed, because his compassions fail not. They are new every morning: great is thy faithfulness.",
                "description": "God's mercies are renewed each morning, making New Year a time of fresh beginnings."
            },
            "12-25": {
                "event": "Christmas - Birth of Christ",
                "reference": "Luke 2:11",
                "text": "For unto you is born this day in the city of David a Saviour, which is Christ the Lord.",
                "description": "The birth of Jesus Christ, our Savior and Lord."
            },
            "6-21": {
                "event": "Summer Solstice - God's Light",
                "reference": "Psalm 84:11",
                "text": "For the LORD God is a sun and shield: the LORD will give grace and glory: no good thing will he withhold from them that walk uprightly.",
                "description": "The longest day celebrates God as our light and source of life."
            }
        }
    
    def get_statistics(self) -> Dict:
        """Get usage statistics."""
        stats = self.statistics.copy()
        stats['books_accessed'] = list(stats['books_accessed'])
        stats['uptime'] = self.start_time.isoformat()
        
        return stats
    
    def set_display_mode(self, mode: str):
        """Set display mode."""
        if mode in ['time', 'date', 'random']:
            self.display_mode = mode
            self.logger.info(f"Display mode changed to: {mode}")
        else:
            raise ValueError(f"Invalid display mode: {mode}")

class VerseScheduler:
    """Handles scheduling of verse updates."""
    
    def __init__(self, verse_manager: VerseManager, update_callback):
        self.verse_manager = verse_manager
        self.update_callback = update_callback
        self.logger = logging.getLogger(__name__)
    
    def schedule_updates(self):
        """Schedule verse updates at the start of each minute."""
        import schedule
        
        schedule.every().minute.at(":00").do(self._update_verse)
        self.logger.info("Verse updates scheduled")
    
    def _update_verse(self):
        """Update the displayed verse."""
        try:
            verse_data = self.verse_manager.get_current_verse()
            self.update_callback(verse_data)
        except Exception as e:
            self.logger.error(f"Verse update failed: {e}")