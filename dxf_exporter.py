"""DXF export functionality."""

import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np
import ezdxf

from image_utils import snap_to_orthogonal

logger = logging.getLogger(__name__)


class DXFExporter:
    """Export floor plans to DXF format."""
    
    def __init__(self, config: Dict):
        """
        Initialize DXF exporter.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.snap_angle = config.get('snap_angle', 12)
    
    def export(
        self,
        lines_by_class: Dict[str, List[Tuple[Tuple[float, float], Tuple[float, float]]]],
        masks: List[np.ndarray],
        output_path: str
    ) -> bool:
        """
        Export floor plan to DXF file.
        
        Args:
            lines_by_class: Dictionary mapping class names to line lists
            masks: List of mask arrays for each class
            output_path: Output DXF file path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create new DXF document
            doc = ezdxf.new('R2010')
            msp = doc.modelspace()
            
            # Create layers
            self._create_layers(doc)
            
            # Add lines for each class
            self._add_lines(msp, lines_by_class)
            
            # Add furniture as blocks
            if 'furn' in self.config['classes']:
                self._add_furniture(msp, masks)
            
            # Add room labels
            if 'wall' in self.config['classes']:
                self._add_room_labels(msp, masks)
            
            # Save DXF file
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            doc.saveas(output_path)
            
            logger.info(f"Exported DXF to: {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export DXF: {e}")
            return False
    
    def _create_layers(self, doc: ezdxf.document.Drawing) -> None:
        """Create DXF layers for different elements."""
        layers = {
            'WALL': 7,      # White
            'DOOR': 3,      # Green
            'WINDOW': 4,    # Cyan
            'FURNITURE': 1  # Red
        }
        
        for layer_name, color in layers.items():
            doc.layers.new(name=layer_name, dxfattribs={'color': color})
    
    def _add_lines(
        self,
        msp,
        lines_by_class: Dict[str, List[Tuple[Tuple[float, float], Tuple[float, float]]]]
    ) -> None:
        """Add lines to model space."""
        for class_name, lines in lines_by_class.items():
            if class_name == 'furn':
                continue  # Handle furniture separately
            
            layer_name = class_name.upper()
            for p1_raw, p2_raw in lines:
                # Snap to orthogonal
                p1, p2 = snap_to_orthogonal((p1_raw, p2_raw), self.snap_angle)
                
                try:
                    msp.add_line(p1, p2, dxfattribs={"layer": layer_name})
                except Exception as e:
                    logger.warning(f"Failed to add line: {e}")
    
    def _add_furniture(self, msp, masks: List[np.ndarray]) -> None:
        """Add furniture as rectangular blocks."""
        try:
            furn_idx = self.config['classes'].index('furn')
            furn_mask = masks[furn_idx]
            
            # Convert to binary
            if furn_mask.dtype != np.uint8:
                furn_mask = (furn_mask * 255).astype(np.uint8)
            
            # Threshold
            furn_mask = (furn_mask > 127).astype(np.uint8)
            
            # Find contours
            contours, _ = cv2.findContours(
                furn_mask,
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            
            for cnt in contours:
                if cv2.contourArea(cnt) < 200:
                    continue
                
                # Get minimum area rectangle
                rect = cv2.minAreaRect(cnt)
                box_pts = cv2.boxPoints(rect)
                box_pts = np.int0(box_pts)
                
                # Add as polyline
                try:
                    msp.add_lwpolyline(
                        box_pts,
                        close=True,
                        dxfattribs={"layer": "FURNITURE"}
                    )
                except Exception as e:
                    logger.warning(f"Failed to add furniture block: {e}")
                    
        except ValueError:
            logger.warning("Furniture class not found in config")
        except Exception as e:
            logger.error(f"Error adding furniture: {e}")
    
    def _add_room_labels(self, msp, masks: List[np.ndarray]) -> None:
        """Add room labels based on wall segmentation."""
        try:
            wall_idx = self.config['classes'].index('wall')
            wall_mask = masks[wall_idx]
            
            # Convert to binary
            if wall_mask.dtype != np.uint8:
                wall_mask = (wall_mask * 255).astype(np.uint8)
            
            wall_mask = (wall_mask > 127).astype(np.uint8)
            
            # Invert to get rooms
            room_mask = cv2.bitwise_not(wall_mask)
            
            # Find connected components (rooms)
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
                room_mask, 8, cv2.CV_32S
            )
            
            # Add text for each room
            for i in range(1, num_labels):  # Skip background (0)
                area = stats[i, cv2.CC_STAT_AREA]
                if area < 500:  # Skip small areas
                    continue
                
                cx, cy = centroids[i]
                label_text = f"ROOM {i}"
                
                try:
                    msp.add_text(
                        label_text,
                        dxfattribs={
                            "height": 12,
                            "color": 2  # Yellow
                        }
                    ).set_pos((cx, cy), align="CENTER")
                except Exception as e:
                    logger.warning(f"Failed to add room label: {e}")
                    
        except ValueError:
            logger.warning("Wall class not found in config")
        except Exception as e:
            logger.error(f"Error adding room labels: {e}")


def extract_lines_from_mask(
    mask: np.ndarray,
    min_length: int = 30,
    max_gap: int = 10
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """
    Extract lines from binary mask using edge detection.
    
    Args:
        mask: Binary mask (0-255 uint8)
        min_length: Minimum line length
        max_gap: Maximum gap in line
        
    Returns:
        List of line tuples ((x1, y1), (x2, y2))
    """
    lines = []
    
    try:
        # Try FastLineDetector first (more accurate)
        fld = cv2.ximgproc.createFastLineDetector(length_threshold=min_length)
        detected = fld.detect(mask)
        
        if detected is not None:
            lines = [
                ((line[0][0], line[0][1]), (line[0][2], line[0][3]))
                for line in detected
            ]
    except AttributeError:
        # Fallback to Hough transform
        logger.warning("FastLineDetector not available, using HoughLinesP")
        
        edges = cv2.Canny(mask, 30, 110)
        detected = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=50,
            minLineLength=min_length,
            maxLineGap=max_gap
        )
        
        if detected is not None:
            lines = [
                ((line[0][0], line[0][1]), (line[0][2], line[0][3]))
                for line in detected
            ]
    
    return lines
