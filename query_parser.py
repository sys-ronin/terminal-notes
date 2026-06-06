# query_parser.py
"""
Central query parser for all search operations.
Handles: action*, type*, g*/global*, in*, date*
"""

import re
from datetime import datetime

class QueryParser:
    # Pattern definitions - add new patterns here easily
    PATTERNS = {
        'actions': {  # This must be a dict, not a set
            'created*': ['CREATED'],
            'create*': ['CREATED'],
            'deleted*': ['DELETED'],
            'delete*': ['DELETED'],
            'edited*': ['UPDATED', 'EDITED'],
            'edit*': ['UPDATED', 'EDITED'],
            'updated*': ['UPDATED', 'EDITED'],
            'update*': ['UPDATED', 'EDITED'],
            'renamed*': ['RENAMED'],
            'rename*': ['RENAMED'],
            'restored*': ['RESTORED'],
            'restore*': ['RESTORED'],
            'erased*': ['ERASED'],
            'erase*': ['ERASED']
        },
        'types': {  # This must be a dict
            'note*': 'note',
            'notes*': 'note',
            'file*': 'file',
            'files*': 'file',
            'notebook*': 'notebook',
            'notebooks*': 'notebook',
            'sub*': 'sub',
            'subnotebook*': 'sub',
            'subnotebooks*': 'sub'
        },
        'global': ['g*', 'global*'],  # This is a list
        'date': r'date\*\s+(\d{2}-\d{2}-\d{4})(?:\s+(\d{2}-\d{2}-\d{4}))?',  # This is a string
        'time_ranges': {  # This must be a dict
            'today*': 'today',
            'yesterday*': 'yesterday',
            'thisweek*': 'thisweek',
            'lastweek*': 'lastweek'
        }
    }
    
    @classmethod
    def parse(cls, query, in_home=True):
        """
        Parse search query into components.
        Order-free except for in* which must be the last token.
        """
        if not query or not query.strip():
            return {
                'actions': None,
                'type': None,
                'date_range': None,
                'scope': None,
                'is_global': False,
                'text': ''
            }

        original = query.strip()
        words = original.split()

        # Step 1: Find in* at the END only
        scope = None
        remaining = original

        if len(words) >= 2 and words[-2] == 'in*':
            scope = {'notebook': words[-1]}
            remaining = ' '.join(words[:-2])
        elif len(words) >= 1 and words[-1].endswith('in*') and len(words[-1]) > 3:
            scope = {'notebook': words[-1][:-3]}
            remaining = ' '.join(words[:-1])

        # Initialize result
        result = {
            'actions': None,
            'type': None,
            'date_range': None,
            'is_global': False,
            'text': '',
            'scope': scope
        }

        if not remaining:
            return result

        # Process remaining words in ANY order
        words = remaining.split()
        text_parts = []
        actions_found = []
        type_found = None
        global_found = False

        for word in words:
            matched = False
        
            # Check actions
            if not matched:
                for pattern, action_list in cls.PATTERNS['actions'].items():
                    if word == pattern:
                        actions_found.extend(action_list)
                        matched = True
                        break
            
            # Check types
            if not matched:
                for pattern, type_val in cls.PATTERNS['types'].items():
                    if word == pattern:
                        type_found = type_val
                        matched = True
                        break
            
            # Check global
            if not matched:
                if word in cls.PATTERNS['global']:
                    global_found = True
                    matched = True
            
            # If not matched any pattern, it's text
            if not matched:
                text_parts.append(word)

        # Set results (deduplicate actions)
        if actions_found:
            result['actions'] = list(set(actions_found))
        result['type'] = type_found
        result['is_global'] = global_found
        result['text'] = ' '.join(text_parts)

        # Check for date pattern
        date_match = re.search(cls.PATTERNS['date'], remaining)
        if date_match:
            try:
                from datetime import datetime as dt
                start_date = dt.strptime(date_match.group(1), '%d-%m-%Y')
                start_date = start_date.replace(hour=0, minute=0, second=0)
            
                if date_match.group(2):
                    end_date = dt.strptime(date_match.group(2), '%d-%m-%Y')
                    end_date = end_date.replace(hour=23, minute=59, second=59)
                else:
                    end_date = start_date.replace(hour=23, minute=59, second=59)
            
                result['date_range'] = (start_date, end_date)
                # Remove date from text if it was captured
                date_text = date_match.group(0)
                if date_text in result['text']:
                    result['text'] = result['text'].replace(date_text, '').strip()
            except ValueError:
                pass
        
        # Check for time range keywords
        if result['date_range'] is None:
            for word in words:
                if word in cls.PATTERNS.get('time_ranges', {}):
                    range_type = cls.PATTERNS['time_ranges'][word]
                    from datetime import datetime, timedelta
                    now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                    
                    if range_type == 'today':
                        start = now
                        end = now.replace(hour=23, minute=59, second=59)
                    elif range_type == 'yesterday':
                        start = now - timedelta(days=1)
                        end = start.replace(hour=23, minute=59, second=59)
                    elif range_type == 'thisweek':
                        start = now - timedelta(days=now.weekday())
                        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
                    elif range_type == 'lastweek':
                        start = now - timedelta(days=now.weekday() + 7)
                        end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
                    
                    result['date_range'] = (start, end)
                    # Remove the keyword from text
                    if word in result['text']:
                        result['text'] = result['text'].replace(word, '').strip()
                    break

        return result
    
    @classmethod
    def format_for_display(cls, parsed):
        """Format parsed query for display (removes wildcards)"""
        parts = []
        if parsed['actions']:
            parts.append(' '.join(parsed['actions']).lower())
        if parsed['type']:
            parts.append(parsed['type'])
        if parsed['text']:
            parts.append(parsed['text'])
        if parsed['scope']:
            parts.append(f"in {parsed['scope']['notebook']}")
        return ' '.join(parts)