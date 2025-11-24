"""Configuration management for Floorplan2DXF."""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages configuration loading and saving."""
    
    DEFAULT_CONFIG = {
        "model_type": "deeplab",
        "encoder": "resnet34",
        "tile_sz": 512,
        "batch_size": 4,  # Optimal for batch normalization, adjusted for GPU memory
        "classes": ["wall", "door", "window", "furn"],
        "train_images": [],
        "mask_folder": "masks",
        "max_epochs": 10,
        "learning_rate": 0.0004,
        "num_workers": 2,
        "overlap": 32,
        "snap_angle": 12,
    }
    
    def __init__(self, work_dir: Path):
        """
        Initialize config manager.
        
        Args:
            work_dir: Working directory path
        """
        self.work_dir = Path(work_dir)
        self.config_path = self.work_dir / "floorplan_config.yaml"
    
    def load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or create default.
        
        Returns:
            Configuration dictionary
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                logger.info(f"Loaded config from {self.config_path}")
                
                # Merge with defaults for missing keys
                for key, value in self.DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                
                return config
            except Exception as e:
                logger.warning(f"Failed to load config: {e}. Using defaults.")
                return self._create_default_config()
        else:
            return self._create_default_config()
    
    def _create_default_config(self) -> Dict[str, Any]:
        """
        Create and save default configuration.
        
        Returns:
            Default configuration dictionary
        """
        config = self.DEFAULT_CONFIG.copy()
        
        # Update paths
        config["mask_folder"] = str(self.work_dir / "masks")
        config["dxf_out"] = str(self.work_dir / "output_dxf" / "output.dxf")
        
        # Find training images
        img_dir = self.work_dir / "images"
        if img_dir.exists():
            image_files = []
            for ext in ['.png', '.jpg', '.jpeg']:
                image_files.extend([str(f) for f in img_dir.glob(f'*{ext}')])
            config["train_images"] = image_files
        
        # Save config
        self.save_config(config)
        return config
    
    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file.
        
        Args:
            config: Configuration dictionary to save
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Saved config to {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def update_config(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update configuration with new values.
        
        Args:
            updates: Dictionary of values to update
            
        Returns:
            Updated configuration
        """
        config = self.load_config()
        config.update(updates)
        self.save_config(config)
        return config
