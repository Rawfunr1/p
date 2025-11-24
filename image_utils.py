"""Image processing utilities."""

import logging
from typing import Tuple, List, Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def tile_image(
    img: np.ndarray,
    tile_size: int = 512,
    overlap: int = 32
) -> Tuple[List[Tuple[Tuple[int, int], np.ndarray]], Tuple[int, int, int, int]]:
    """
    Split image into overlapping tiles.
    
    Args:
        img: Input image array
        tile_size: Size of each tile
        overlap: Overlap between tiles
        
    Returns:
        Tuple of (tiles_list, info) where:
        - tiles_list: List of ((x, y), tile_array) tuples
        - info: (height, width, tile_size, overlap)
    """
    h, w = img.shape[:2]
    tiles = []
    step = tile_size - overlap
    
    for y in range(0, h, step):
        for x in range(0, w, step):
            y2 = min(y + tile_size, h)
            x2 = min(x + tile_size, w)
            tile = img[y:y2, x:x2]
            
            # Pad if necessary
            if tile.shape[0] < tile_size or tile.shape[1] < tile_size:
                tile = cv2.copyMakeBorder(
                    tile,
                    0, tile_size - tile.shape[0],
                    0, tile_size - tile.shape[1],
                    cv2.BORDER_CONSTANT,
                    value=0
                )
            
            tiles.append(((x, y), tile))
    
    return tiles, (h, w, tile_size, overlap)


def stitch_mask(
    tiles: List[Tuple[Tuple[int, int], np.ndarray]],
    info: Tuple[int, int, int, int]
) -> np.ndarray:
    """
    Stitch tiles back into full mask with overlap blending.
    
    Args:
        tiles: List of ((x, y), tile_pred) tuples
        info: (height, width, tile_size, overlap) from tile_image
        
    Returns:
        Stitched mask array
    """
    h, w, tile_size, overlap = info
    out_mask = np.zeros((h, w), dtype=np.float32)
    count = np.zeros((h, w), dtype=np.float32)
    
    for (x, y), tile_pred in tiles:
        h_crop = min(tile_size, h - y)
        w_crop = min(tile_size, w - x)
        
        out_mask[y:y + h_crop, x:x + w_crop] += tile_pred[:h_crop, :w_crop]
        count[y:y + h_crop, x:x + w_crop] += 1
    
    # Avoid division by zero
    result = np.divide(
        out_mask,
        count,
        out=np.zeros_like(out_mask),
        where=count != 0
    )
    
    return result


def clean_mask(mask: np.ndarray, kernel_size: int = 5) -> np.ndarray:
    """
    Clean mask using morphological operations.
    
    Args:
        mask: Input mask (0-255 uint8)
        kernel_size: Size of morphological kernel
        
    Returns:
        Cleaned mask
    """
    if mask.dtype != np.uint8:
        mask = (mask * 255).astype(np.uint8)
    
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    
    # Close small gaps
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    
    # Remove small noise
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
    
    return opened


def snap_to_orthogonal(
    line_points: Tuple[Tuple[float, float], Tuple[float, float]],
    snap_angle: float = 12.0
) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Snap lines to horizontal or vertical if close enough.
    
    Args:
        line_points: ((x1, y1), (x2, y2))
        snap_angle: Angle threshold in degrees
        
    Returns:
        Snapped line points
    """
    p1, p2 = line_points
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return p1, p2
    
    angle_rad = np.arctan2(dy, dx)
    angle_deg = np.rad2deg(angle_rad) % 180
    
    # Snap to horizontal
    if abs(angle_deg) < snap_angle or abs(angle_deg - 180) < snap_angle:
        return (p1[0], p1[1]), (p2[0], p1[1])
    
    # Snap to vertical
    if abs(angle_deg - 90) < snap_angle:
        return (p1[0], p1[1]), (p1[0], p2[1])
    
    return p1, p2


def load_image_safe(image_path: str) -> Optional[np.ndarray]:
    """
    Safely load image with error handling.
    
    Args:
        image_path: Path to image file
        
    Returns:
        Image array or None if loading failed
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            return None
        return img
    except Exception as e:
        logger.error(f"Error loading image {image_path}: {e}")
        return None


def save_image_safe(
    image: np.ndarray,
    output_path: str,
    quality: int = 95
) -> bool:
    """
    Safely save image with error handling.
    
    Args:
        image: Image array to save
        output_path: Output file path
        quality: JPEG quality (1-100)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if output_path.lower().endswith('.jpg') or output_path.lower().endswith('.jpeg'):
            cv2.imwrite(output_path, image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        else:
            cv2.imwrite(output_path, image)
        return True
    except Exception as e:
        logger.error(f"Error saving image to {output_path}: {e}")
        return False


def create_visualization(
    image: np.ndarray,
    masks: List[np.ndarray],
    colors: Optional[List[Tuple[int, int, int]]] = None
) -> np.ndarray:
    """
    Create visualization overlay of masks on image.
    
    Args:
        image: Base image (BGR)
        masks: List of mask arrays (0-255 uint8)
        colors: List of (B, G, R) colors for each mask
        
    Returns:
        Visualization image
    """
    if colors is None:
        colors = [
            (0, 0, 255),    # Red for walls
            (0, 255, 0),    # Green for doors
            (255, 0, 0),    # Blue for windows
            (0, 255, 255)   # Yellow for furniture
        ]
    
    overlay = image.copy()
    
    for idx, mask in enumerate(masks):
        if idx >= len(colors):
            break
        
        color = colors[idx]
        color_mask = np.zeros_like(image)
        color_mask[:] = color
        
        # Create alpha channel from mask
        mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR) if len(mask.shape) == 2 else mask
        
        # Blend where mask is active
        overlay = np.where(
            mask_3ch > 127,
            cv2.addWeighted(overlay, 0.7, color_mask, 0.3, 0),
            overlay
        )
    
    return overlay
