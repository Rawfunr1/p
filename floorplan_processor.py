"""Main floor plan processing logic."""

import logging
import gc
from pathlib import Path
from typing import Dict, Any, List, Optional

import torch
import torch.nn as nn
import numpy as np
import cv2
from torch.utils.data import DataLoader
from torchvision import transforms
from PIL import Image
from tqdm import tqdm

from model_builder import ModelBuilder
from dataset import FloorplanDataset, collate_fn
from image_utils import (
    tile_image, stitch_mask, clean_mask,
    create_visualization, load_image_safe
)
from dxf_exporter import DXFExporter, extract_lines_from_mask
from model_3d_exporter import Model3DExporter

logger = logging.getLogger(__name__)


class FloorplanProcessor:
    """Main processor for floor plan conversion."""
    
    def __init__(
        self,
        config: Dict[str, Any],
        work_dir: Path,
        checkpoint_dir: Path
    ):
        """
        Initialize processor.
        
        Args:
            config: Configuration dictionary
            work_dir: Working directory
            checkpoint_dir: Checkpoint directory
        """
        self.config = config
        self.work_dir = Path(work_dir)
        self.checkpoint_dir = Path(checkpoint_dir)
        
        self.classes = config.get('classes', ['wall', 'door', 'window', 'furn'])
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Initialize model builder
        self.model_builder = ModelBuilder(config, checkpoint_dir)
        self.model = self.model_builder.build_model(self.classes)
        self.optimizer = self.model_builder.get_optimizer(self.model)
        
        # Load checkpoint if exists
        self.start_epoch = self.model_builder.load_checkpoint(
            self.model,
            self.optimizer
        )
        
        logger.info(f"Initialized processor with {len(self.classes)} classes")
    
    def train(self) -> None:
        """Train the segmentation model."""
        train_images = self.config.get('train_images', [])
        
        if not train_images:
            logger.warning("No training images available")
            return
        
        logger.info(f"Training on {len(train_images)} images")
        
        # Create dataset
        dataset = FloorplanDataset(
            image_paths=train_images,
            mask_folder=self.config['mask_folder'],
            classes=self.classes,
            tile_size=self.config.get('tile_sz', 512),
            overlap=self.config.get('overlap', 32),
            augment=True
        )
        
        # Create dataloader
        dataloader = DataLoader(
            dataset,
            batch_size=1,  # Process one image at a time
            shuffle=True,
            num_workers=self.config.get('num_workers', 2),
            collate_fn=collate_fn,
            pin_memory=True if torch.cuda.is_available() else False
        )
        
        # Get loss function
        loss_fn = self.model_builder.get_loss_function()
        
        # Training loop
        max_epochs = self.config.get('max_epochs', 10)
        best_loss = float('inf')
        
        for epoch in range(self.start_epoch, max_epochs):
            self.model.train()
            total_loss = 0.0
            num_batches = 0
            
            pbar = tqdm(dataloader, desc=f"Epoch {epoch + 1}/{max_epochs}")
            
            for images, masks in pbar:
                # Move to device
                images = images.to(self.device)
                masks = masks.to(self.device)
                
                # Handle batch normalization edge case
                if images.shape[0] == 1:
                    # Duplicate to avoid BN error
                    images = torch.cat([images, images], dim=0)
                    masks = torch.cat([masks, masks], dim=0)
                
                # Forward pass
                self.optimizer.zero_grad()
                outputs = self.model(images)
                
                # Calculate loss
                loss = loss_fn(outputs, masks)
                
                # Backward pass
                loss.backward()
                self.optimizer.step()
                
                # Update metrics
                batch_loss = loss.item()
                total_loss += batch_loss
                num_batches += 1
                
                pbar.set_postfix({'loss': f'{batch_loss:.4f}'})
                
                # Clear cache
                del outputs, loss
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            
            # Calculate average loss
            avg_loss = total_loss / max(num_batches, 1)
            logger.info(f"Epoch {epoch + 1}/{max_epochs} - Loss: {avg_loss:.4f}")
            
            # Save checkpoint
            is_best = avg_loss < best_loss
            if is_best:
                best_loss = avg_loss
                logger.info(f"New best model with loss: {avg_loss:.4f}")
            
            self.model_builder.save_checkpoint(
                self.model,
                self.optimizer,
                epoch,
                avg_loss,
                is_best=is_best
            )
            
            # Cleanup
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        logger.info("Training complete")
    
    def process_image(self, image_path: str) -> bool:
        """
        Process a single image and export results.
        
        Args:
            image_path: Path to input image
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing image: {image_path}")
        
        # Load image
        img = load_image_safe(image_path)
        if img is None:
            return False
        
        # Predict masks
        masks = self._predict_masks(img)
        if masks is None:
            return False
        
        # Clean masks
        masks_clean = [clean_mask((m * 255).astype(np.uint8)) for m in masks]
        
        # Create output directory
        output_dir = self.work_dir / 'output'
        output_dir.mkdir(exist_ok=True)
        
        # Create visualization
        img_name = Path(image_path).stem
        vis_img = create_visualization(img, masks_clean)
        vis_path = output_dir / f'{img_name}_visualization.png'
        cv2.imwrite(str(vis_path), vis_img)
        logger.info(f"Saved visualization: {vis_path}")
        
        # Extract lines for DXF
        lines_by_class = self._extract_lines(masks_clean)
        
        # Export DXF
        dxf_path = output_dir / f'{img_name}.dxf'
        dxf_exporter = DXFExporter(self.config)
        dxf_exporter.export(lines_by_class, masks_clean, str(dxf_path))
        
        # Export 3D model
        try:
            glb_path = output_dir / f'{img_name}.glb'
            exporter_3d = Model3DExporter()
            
            wall_idx = self.classes.index('wall')
            door_idx = self.classes.index('door')
            window_idx = self.classes.index('window')
            furn_idx = self.classes.index('furn')
            
            exporter_3d.export(
                masks_clean[wall_idx],
                masks_clean[door_idx],
                masks_clean[window_idx],
                masks_clean[furn_idx],
                str(glb_path)
            )
        except (ValueError, Exception) as e:
            logger.warning(f"3D export failed: {e}")
        
        # Cleanup
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        logger.info(f"Processing complete for {image_path}")
        return True
    
    def _predict_masks(self, img: np.ndarray) -> Optional[List[np.ndarray]]:
        """
        Predict segmentation masks for image.
        
        Args:
            img: Input image (BGR)
            
        Returns:
            List of mask arrays or None if failed
        """
        try:
            tile_size = self.config.get('tile_sz', 512)
            overlap = self.config.get('overlap', 32)
            
            # Tile image
            tiles, info = tile_image(img, tile_size, overlap)
            
            # Predict on each tile
            self.model.eval()
            seg_predictions = []
            
            with torch.no_grad():
                for (x, y), tile in tiles:
                    # Convert to tensor
                    tile_rgb = cv2.cvtColor(tile, cv2.COLOR_BGR2RGB)
                    tile_pil = Image.fromarray(tile_rgb)
                    tile_tensor = transforms.ToTensor()(tile_pil)
                    tile_tensor = tile_tensor.unsqueeze(0).to(self.device)
                    
                    # Predict
                    output = self.model(tile_tensor)
                    seg = output[0].cpu().numpy()
                    
                    seg_predictions.append(((x, y), seg))
            
            # Stitch masks
            masks = []
            for class_idx in range(len(self.classes)):
                mask = stitch_mask(
                    [((x, y), seg[class_idx]) for (x, y), seg in seg_predictions],
                    info
                )
                masks.append(mask)
            
            return masks
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return None
    
    def _extract_lines(
        self,
        masks: List[np.ndarray]
    ) -> Dict[str, List]:
        """
        Extract lines from masks for each class.
        
        Args:
            masks: List of mask arrays
            
        Returns:
            Dictionary mapping class names to line lists
        """
        lines_by_class = {}
        
        for idx, class_name in enumerate(self.classes):
            if class_name == 'furn':
                # Handle furniture separately (as blocks)
                lines_by_class[class_name] = []
                continue
            
            mask = masks[idx]
            lines = extract_lines_from_mask(mask)
            lines_by_class[class_name] = lines
            
            logger.debug(f"Extracted {len(lines)} lines for {class_name}")
        
        return lines_by_class
