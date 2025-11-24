#!/usr/bin/env python3
"""
Floorplan to DXF/3D Converter - Main Entry Point
Fixed and optimized version with proper error handling and structure
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies() -> bool:
    """Check if all required dependencies are installed."""
    required_modules = [
        'torch',
        'cv2',
        'numpy',
        'PIL',
        'yaml',
        'segmentation_models_pytorch',
        'ezdxf',
        'trimesh',
        'shapely',
        'skimage'
    ]
    
    missing = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        logger.error(f"Missing required dependencies: {', '.join(missing)}")
        logger.info("Install them with: pip install -r requirements.txt")
        return False
    
    return True


def setup_environment() -> tuple[Path, Path]:
    """
    Setup working directories and configuration.
    
    Returns:
        Tuple of (work_dir, checkpoint_dir)
    """
    # Determine working directory
    if os.path.exists('/kaggle'):
        work_dir = Path('/kaggle/working/Floorplan2DXF_Advanced_PRO')
    else:
        work_dir = Path('./Floorplan2DXF_Output')
    
    # Create necessary directories
    work_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = work_dir / 'checkpoints'
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories
    (work_dir / 'images').mkdir(exist_ok=True)
    (work_dir / 'masks').mkdir(exist_ok=True)
    (work_dir / 'output_dxf').mkdir(exist_ok=True)
    
    logger.info(f"Working directory: {work_dir}")
    return work_dir, checkpoint_dir


def main() -> int:
    """Main entry point."""
    try:
        logger.info("Starting Floorplan2DXF Converter")
        
        # Check dependencies
        if not check_dependencies():
            logger.error("Dependency check failed")
            return 1
        
        # Setup environment
        work_dir, checkpoint_dir = setup_environment()
        
        logger.info("Environment setup complete")
        logger.info(f"Working directory: {work_dir}")
        logger.info(f"Checkpoint directory: {checkpoint_dir}")
        
        # Import modules after dependency check
        from floorplan_processor import FloorplanProcessor
        from config_manager import ConfigManager
        
        # Load or create configuration
        config_manager = ConfigManager(work_dir)
        config = config_manager.load_config()
        
        # Initialize processor
        processor = FloorplanProcessor(config, work_dir, checkpoint_dir)
        
        # Check if training images are available
        if config.get('train_images'):
            logger.info(f"Found {len(config['train_images'])} training images")
            # Train model
            processor.train()
        else:
            logger.warning("No training images found, skipping training")
        
        # Process images if any exist
        image_dir = work_dir / 'images'
        image_files = list(image_dir.glob('*.png')) + \
                     list(image_dir.glob('*.jpg')) + \
                     list(image_dir.glob('*.jpeg'))
        
        if image_files:
            logger.info(f"Processing {len(image_files)} images")
            for img_path in image_files:
                processor.process_image(str(img_path))
        else:
            logger.warning("No images found to process")
        
        logger.info("Processing complete")
        return 0
        
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
