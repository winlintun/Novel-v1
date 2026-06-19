#!/usr/bin/env python3
"""
Model-presets loader for the Web UI dropdown and the --compare-models tool.

The model catalog lives in the single config file (config/settings.yaml) under
the `model_presets:` section. To change the model used for translation, edit the
`models:` block or run `python scripts/change_model.py`.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List

_DEFAULT_PRESETS = {
    'active_model': 'padauk-gemma-q8',
    'models': {
        'padauk-gemma-q8': {
            'name': 'padauk-gemma:q8_0',
            'display_name': 'Padauk-Gemma Q8 (Recommended)',
            'temperature': 0.2,
            'max_tokens': 4096,
            'repeat_penalty': 1.3,
            'chunk_size': 2500,
        }
    },
}


class SkeletonModelManager:
    """Reads the `model_presets:` section of config/settings.yaml."""

    def __init__(self, config_path: str = "config/settings.yaml"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()

    def _load_config(self):
        """Load the `model_presets` section from the single settings file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                settings = yaml.safe_load(f) or {}
            self._config = settings.get('model_presets') or dict(_DEFAULT_PRESETS)
        except Exception as e:
            print(f"Error loading model presets: {e}")
            self._config = dict(_DEFAULT_PRESETS)
    
    def get_all_models(self) -> Dict[str, Dict[str, Any]]:
        """Get all model definitions"""
        return self._config.get('models', {})
    
    def get_model(self, model_key: str) -> Optional[Dict[str, Any]]:
        """Get a specific model by key"""
        return self._config.get('models', {}).get(model_key)
    
    def get_active_model_key(self) -> str:
        """Get the active model key"""
        return self._config.get('active_model', 'padauk-gemma-q8')
    
    def get_active_model(self) -> Optional[Dict[str, Any]]:
        """Get the currently active model definition"""
        active_key = self.get_active_model_key()
        return self.get_model(active_key)
    
    def set_active_model(self, model_key: str) -> bool:
        """Set the active model"""
        if model_key not in self._config.get('models', {}):
            return False
        
        self._config['active_model'] = model_key
        return self._save_config()
    
    def get_models_for_dropdown(self) -> List[Dict[str, Any]]:
        """Get models formatted for Web UI dropdown"""
        models = []
        for key, data in self._config.get('models', {}).items():
            models.append({
                'key': key,
                'name': data.get('name', key),
                'display_name': data.get('display_name', key),
                'description': data.get('description', ''),
                'category': data.get('category', 'myanmar'),
                'temperature': data.get('temperature', 0.2),
                'max_tokens': data.get('max_tokens', 4096),
                'repeat_penalty': data.get('repeat_penalty', 1.3),
                'chunk_size': data.get('chunk_size', 2500),
                'vram_gb': data.get('vram_gb', 4)
            })
        return models
    
    def get_models_by_category(self) -> Dict[str, Dict[str, Any]]:
        """Get models grouped by category for Web UI"""
        categories = {}
        cat_config = self._config.get('categories', {})
        
        for key, data in self._config.get('models', {}).items():
            cat = data.get('category', 'myanmar')
            if cat not in categories:
                cat_info = cat_config.get(cat, {})
                categories[cat] = {
                    'label': cat_info.get('label', cat.capitalize()),
                    'description': cat_info.get('description', ''),
                    'models': []
                }
            
            categories[cat]['models'].append({
                'key': key,
                'name': data.get('name', key),
                'display_name': data.get('display_name', key),
                'description': data.get('description', ''),
                'temperature': data.get('temperature', 0.2),
                'max_tokens': data.get('max_tokens', 4096),
                'repeat_penalty': data.get('repeat_penalty', 1.3),
                'chunk_size': data.get('chunk_size', 2500),
                'vram_gb': data.get('vram_gb', 4)
            })
        
        return categories
    
    def apply_model_to_config(self, model_key: str, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a model's settings to a base configuration"""
        import copy
        config = copy.deepcopy(base_config)
        model = self.get_model(model_key)
        
        if not model:
            return config
        
        # Apply model name to all roles
        model_name = model.get('name', model_key)
        if 'models' not in config:
            config['models'] = {}
        config['models']['translator'] = model_name
        config['models']['editor'] = model_name
        config['models']['refiner'] = model_name
        config['models']['checker'] = model_name
        
        # Apply processing parameters
        if 'processing' not in config:
            config['processing'] = {}
        config['processing']['temperature'] = model.get('temperature', 0.2)
        config['processing']['max_tokens'] = model.get('max_tokens', 4096)
        config['processing']['repeat_penalty'] = model.get('repeat_penalty', 1.3)
        config['processing']['chunk_size'] = model.get('chunk_size', 2500)
        
        # Apply to pipeline
        if 'translation_pipeline' not in config:
            config['translation_pipeline'] = {}
        config['translation_pipeline']['stage1_model'] = model_name
        config['translation_pipeline']['stage2_model'] = model_name
        
        return config
    
    def _save_config(self) -> bool:
        """Persist the model_presets section back into settings.yaml."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                settings = yaml.safe_load(f) or {}
            settings['model_presets'] = self._config
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(settings, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"Error saving model presets: {e}")
            return False


# Global instance
_skeleton_manager = None

def get_skeleton_manager() -> SkeletonModelManager:
    """Get or create the global skeleton manager instance"""
    global _skeleton_manager
    if _skeleton_manager is None:
        _skeleton_manager = SkeletonModelManager()
    return _skeleton_manager
