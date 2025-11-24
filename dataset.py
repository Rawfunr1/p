"""Dataset classes for training."""

import os
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset
from torchvision import transforms
from PIL import Image

from image_utils import tile_image

logger = logging.getLogger(__name__)


class FloorplanDataset(Dataset):
    """Dataset for floor plan segmentation."""
    
    def __init__(
        self,
        image_paths: List[str],
        mask_folder: str,
        classes: List[str],
        tile_size: int = 512,
        overlap: int = 32,
        transform: Optional[transforms.Compose] = None,
        augment: bool = True
    ):
        """
        Initialize dataset.
        
        Args:
            image_paths: List of image file paths
            mask_folder: Folder containing mask files
            classes: List of class names
            tile_size: Size of tiles
            overlap: Overlap between tiles
            transform: Optional transform to apply
            augment: Whether to apply augmentation
        """
        self.image_paths = image_paths
        self.mask_folder = Path(mask_folder)
        self.classes = classes
        self.tile_size = tile_size
        self.overlap = overlap
        self.augment = augment
        
        # Setup transforms
        if transform is None:
            if augment:
                self.transform = get_augmentation_transform()
            else:
                self.transform = get_basic_transform()
        else:
            self.transform = transform
    
    def __len__(self) -> int:
        """Return number of images."""
        return len(self.image_paths)
    
    def __getitem__(self, idx: int):
        """
        Get item from dataset.
        
        Args:
            idx: Index
            
        Returns:
            Tuple of (image_tiles, mask_tiles)
        """
        img_path = self.image_paths[idx]
        
        # Load image
        img = cv2.imread(img_path)
        if img is None:
            logger.warning(f"Failed to load image: {img_path}")
            # Return empty tensors
            return (
                torch.zeros((1, 3, self.tile_size, self.tile_size)),
                torch.zeros((1, len(self.classes), self.tile_size, self.tile_size))
            )
        
        # Load masks for all classes
        img_name = Path(img_path).stem
        loaded_masks = {}
        
        for class_name in self.classes:
            mask_path = self.mask_folder / f"{img_name}_{class_name}.png"
            if mask_path.exists():
                mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
                loaded_masks[class_name] = mask
            else:
                logger.debug(f"Mask not found: {mask_path}")
                loaded_masks[class_name] = None
        
        # Tile image
        tiles, _ = tile_image(img, self.tile_size, self.overlap)
        
        all_img_tiles = []
        all_mask_tiles = []
        
        for (x, y), tile in tiles:
            # Transform image tile
            tile_pil = Image.fromarray(cv2.cvtColor(tile, cv2.COLOR_BGR2RGB))
            img_tensor = self.transform(tile_pil)
            
            # Process mask tiles
            mask_tensors = []
            for class_name in self.classes:
                mask = loaded_masks[class_name]
                
                if mask is not None:
                    # Extract corresponding tile from mask
                    h_m, w_m = mask.shape
                    y_end = min(y + self.tile_size, h_m)
                    x_end = min(x + self.tile_size, w_m)
                    mask_tile = mask[y:y_end, x:x_end]
                    
                    # Pad if necessary
                    if mask_tile.shape[0] < self.tile_size or mask_tile.shape[1] < self.tile_size:
                        mask_tile = cv2.copyMakeBorder(
                            mask_tile,
                            0, self.tile_size - mask_tile.shape[0],
                            0, self.tile_size - mask_tile.shape[1],
                            cv2.BORDER_CONSTANT,
                            value=0
                        )
                else:
                    # No mask available for this class
                    mask_tile = np.zeros((self.tile_size, self.tile_size), dtype=np.uint8)
                
                # Normalize to [0, 1]
                mask_tensor = torch.from_numpy(mask_tile.astype(np.float32) / 255.0)
                mask_tensors.append(mask_tensor)
            
            all_img_tiles.append(img_tensor)
            all_mask_tiles.append(torch.stack(mask_tensors))
        
        # Stack all tiles
        return torch.stack(all_img_tiles), torch.stack(all_mask_tiles)


def get_basic_transform() -> transforms.Compose:
    """Get basic image transform (no augmentation)."""
    return transforms.Compose([
        transforms.ToTensor(),
    ])


def get_augmentation_transform() -> transforms.Compose:
    """Get augmented image transform."""
    return transforms.Compose([
        transforms.ColorJitter(
            brightness=0.2,
            contrast=0.2,
            saturation=0.1,
            hue=0.05
        ),
        transforms.ToTensor(),
    ])


def collate_fn(batch):
    """
    Custom collate function to handle variable-sized tile batches.
    
    Args:
        batch: List of (img_tiles, mask_tiles) tuples
        
    Returns:
        Tuple of (batched_images, batched_masks)
    """
    # Flatten all tiles from all images in batch
    all_imgs = []
    all_masks = []
    
    for img_tiles, mask_tiles in batch:
        # img_tiles: (num_tiles, C, H, W)
        # mask_tiles: (num_tiles, num_classes, H, W)
        all_imgs.append(img_tiles)
        all_masks.append(mask_tiles)
    
    # Concatenate along tile dimension
    batched_imgs = torch.cat(all_imgs, dim=0)
    batched_masks = torch.cat(all_masks, dim=0)
    
    return batched_imgs, batched_masks
