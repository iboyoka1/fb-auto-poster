"""
Content management: templates, drafts, and A/B rotation
"""
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional
import random
import re

try:
    from config import PROJECT_ROOT, ENABLE_CONTENT_TEMPLATES
except ImportError:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    ENABLE_CONTENT_TEMPLATES = True

try:
    from logger import get_logger
    logger = get_logger("content")
except ImportError:
    import logging
    logger = logging.getLogger("content")


def spin_text(text: str) -> str:
    """
    Process spintax text and return a random variation
    Example: "{Hello|Hi|Hey} {world|everyone}" -> "Hi everyone"
    """
    def replace_spin(match):
        options = match.group(1).split('|')
        return random.choice(options)
    
    # Keep spinning until no more spintax patterns found
    max_iterations = 100  # Prevent infinite loops
    for _ in range(max_iterations):
        new_text = re.sub(r'\{([^{}]+)\}', replace_spin, text)
        if new_text == text:
            break
        text = new_text
    
    return text


def get_content_variations(base_content: str, count: int = 5) -> List[str]:
    """Generate multiple variations of content using spintax"""
    variations = []
    attempts = 0
    max_attempts = count * 3
    
    while len(variations) < count and attempts < max_attempts:
        variation = spin_text(base_content)
        if variation not in variations:
            variations.append(variation)
        attempts += 1
    
    return variations


class ContentTemplateManager:
    """
    Manage reusable content templates
    """
    
    def __init__(self, templates_file: str = None):
        self.templates_file = templates_file or os.path.join(PROJECT_ROOT, "content_templates.json")
        self.templates = self.load_templates()
    
    def load_templates(self) -> List[Dict]:
        """Load templates from file"""
        try:
            if os.path.exists(self.templates_file):
                with open(self.templates_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading templates: {e}")
            return []
    
    def save_templates(self) -> bool:
        """Save templates to file"""
        try:
            with open(self.templates_file, 'w', encoding='utf-8') as f:
                json.dump(self.templates, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving templates: {e}")
            return False
    
    def create_template(
        self,
        name: str,
        content: str,
        category: str = "general",
        tags: List[str] = None,
        variables: Dict[str, str] = None,
    ) -> Dict:
        """
        Create a new content template
        
        Args:
            name: Template name
            content: Template content (supports spintax and {{variables}})
            category: Category for organization
            tags: List of tags for filtering
            variables: Default values for template variables
        """
        template = {
            'id': int(time.time() * 1000),
            'name': name,
            'content': content,
            'category': category,
            'tags': tags or [],
            'variables': variables or {},
            'use_count': 0,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
        
        self.templates.append(template)
        self.save_templates()
        
        return {'success': True, 'template': template}
    
    def get_template(self, template_id: int) -> Optional[Dict]:
        """Get a template by ID"""
        for t in self.templates:
            if t['id'] == template_id:
                return t
        return None
    
    def update_template(self, template_id: int, updates: Dict) -> bool:
        """Update a template"""
        for t in self.templates:
            if t['id'] == template_id:
                for key, value in updates.items():
                    if key not in ('id', 'created_at'):
                        t[key] = value
                t['updated_at'] = datetime.now().isoformat()
                self.save_templates()
                return True
        return False
    
    def delete_template(self, template_id: int) -> bool:
        """Delete a template"""
        original_len = len(self.templates)
        self.templates = [t for t in self.templates if t['id'] != template_id]
        if len(self.templates) < original_len:
            self.save_templates()
            return True
        return False
    
    def render_template(self, template_id: int, variables: Dict[str, str] = None) -> Optional[str]:
        """
        Render a template with variable substitution
        
        Args:
            template_id: Template ID
            variables: Variables to substitute (overrides defaults)
            
        Returns:
            Rendered content or None if template not found
        """
        template = self.get_template(template_id)
        if not template:
            return None
        
        content = template['content']
        
        # Merge default variables with provided ones
        all_vars = {**template.get('variables', {}), **(variables or {})}
        
        # Substitute {{variable}} patterns
        for key, value in all_vars.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
        
        # Process spintax
        content = spin_text(content)
        
        # Update use count
        template['use_count'] = template.get('use_count', 0) + 1
        self.save_templates()
        
        return content
    
    def get_templates_by_category(self, category: str) -> List[Dict]:
        """Get all templates in a category"""
        return [t for t in self.templates if t.get('category') == category]
    
    def get_templates_by_tag(self, tag: str) -> List[Dict]:
        """Get all templates with a specific tag"""
        return [t for t in self.templates if tag in t.get('tags', [])]
    
    def search_templates(self, query: str) -> List[Dict]:
        """Search templates by name or content"""
        query = query.lower()
        return [
            t for t in self.templates
            if query in t['name'].lower() or query in t['content'].lower()
        ]
    
    def get_all_templates(self) -> List[Dict]:
        """Get all templates"""
        return self.templates
    
    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        return list(set(t.get('category', 'general') for t in self.templates))


class DraftManager:
    """
    Manage draft posts (work in progress)
    """
    
    def __init__(self, drafts_file: str = None):
        self.drafts_file = drafts_file or os.path.join(PROJECT_ROOT, "drafts.json")
        self.drafts = self.load_drafts()
    
    def load_drafts(self) -> List[Dict]:
        """Load drafts from file"""
        try:
            if os.path.exists(self.drafts_file):
                with open(self.drafts_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading drafts: {e}")
            return []
    
    def save_drafts(self) -> bool:
        """Save drafts to file"""
        try:
            with open(self.drafts_file, 'w', encoding='utf-8') as f:
                json.dump(self.drafts, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logger.error(f"Error saving drafts: {e}")
            return False
    
    def create_draft(
        self,
        content: str,
        title: str = None,
        groups: List[str] = None,
        media_files: List[str] = None,
    ) -> Dict:
        """Create a new draft"""
        draft = {
            'id': int(time.time() * 1000),
            'title': title or f"Draft {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            'content': content,
            'groups': groups or [],
            'media_files': media_files or [],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
        }
        
        self.drafts.append(draft)
        self.save_drafts()
        
        return {'success': True, 'draft': draft}
    
    def update_draft(self, draft_id: int, updates: Dict) -> bool:
        """Update a draft"""
        for d in self.drafts:
            if d['id'] == draft_id:
                for key, value in updates.items():
                    if key not in ('id', 'created_at'):
                        d[key] = value
                d['updated_at'] = datetime.now().isoformat()
                self.save_drafts()
                return True
        return False
    
    def delete_draft(self, draft_id: int) -> bool:
        """Delete a draft"""
        original_len = len(self.drafts)
        self.drafts = [d for d in self.drafts if d['id'] != draft_id]
        if len(self.drafts) < original_len:
            self.save_drafts()
            return True
        return False
    
    def get_draft(self, draft_id: int) -> Optional[Dict]:
        """Get a draft by ID"""
        for d in self.drafts:
            if d['id'] == draft_id:
                return d
        return None
    
    def get_all_drafts(self) -> List[Dict]:
        """Get all drafts"""
        return sorted(self.drafts, key=lambda x: x['updated_at'], reverse=True)


class ContentRotator:
    """
    A/B testing and content rotation
    """
    
    def __init__(self):
        self.rotation_history: Dict[int, List[int]] = {}  # post_id -> list of variant indices used
    
    def create_ab_test(
        self,
        variants: List[str],
        weights: List[float] = None,
    ) -> Dict:
        """
        Create an A/B test configuration
        
        Args:
            variants: List of content variations
            weights: Optional weights for each variant (must sum to 1.0)
        """
        if not variants:
            return {'success': False, 'error': 'At least one variant required'}
        
        if weights is None:
            # Equal distribution
            weights = [1.0 / len(variants)] * len(variants)
        
        if len(weights) != len(variants):
            return {'success': False, 'error': 'Weights count must match variants count'}
        
        return {
            'success': True,
            'test': {
                'variants': variants,
                'weights': weights,
                'results': [{'impressions': 0, 'success': 0} for _ in variants],
            }
        }
    
    def select_variant(self, test: Dict) -> tuple[int, str]:
        """
        Select a variant based on weights
        
        Returns:
            (variant_index, variant_content)
        """
        variants = test['variants']
        weights = test.get('weights', [1.0 / len(variants)] * len(variants))
        
        # Weighted random selection
        r = random.random()
        cumulative = 0
        for i, weight in enumerate(weights):
            cumulative += weight
            if r <= cumulative:
                return i, variants[i]
        
        return len(variants) - 1, variants[-1]
    
    def record_result(self, test: Dict, variant_index: int, success: bool):
        """Record the result of a variant use"""
        if 'results' not in test:
            test['results'] = [{'impressions': 0, 'success': 0} for _ in test['variants']]
        
        test['results'][variant_index]['impressions'] += 1
        if success:
            test['results'][variant_index]['success'] += 1
    
    def get_best_variant(self, test: Dict) -> tuple[int, float]:
        """
        Get the best performing variant
        
        Returns:
            (variant_index, success_rate)
        """
        results = test.get('results', [])
        if not results:
            return 0, 0.0
        
        best_idx = 0
        best_rate = 0.0
        
        for i, result in enumerate(results):
            impressions = result.get('impressions', 0)
            if impressions > 0:
                rate = result.get('success', 0) / impressions
                if rate > best_rate:
                    best_rate = rate
                    best_idx = i
        
        return best_idx, best_rate
    
    def get_stats(self, test: Dict) -> Dict:
        """Get statistics for all variants"""
        stats = []
        for i, result in enumerate(test.get('results', [])):
            impressions = result.get('impressions', 0)
            success = result.get('success', 0)
            rate = success / impressions if impressions > 0 else 0.0
            
            stats.append({
                'variant_index': i,
                'content_preview': test['variants'][i][:50] + '...' if len(test['variants'][i]) > 50 else test['variants'][i],
                'impressions': impressions,
                'success': success,
                'success_rate': round(rate * 100, 1),
            })
        
        return {'variants': stats}


# Global instances
template_manager = ContentTemplateManager()
draft_manager = DraftManager()
content_rotator = ContentRotator()
