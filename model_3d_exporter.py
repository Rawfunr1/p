"""3D model export functionality."""

import logging
from typing import Optional
import gc

import numpy as np

logger = logging.getLogger(__name__)


class Model3DExporter:
    """Export floor plans to 3D models (GLB format)."""
    
    def __init__(self, wall_height: float = 100.0, furniture_height: float = 30.0):
        """
        Initialize 3D exporter.
        
        Args:
            wall_height: Height of walls in 3D model
            furniture_height: Height of furniture in 3D model
        """
        self.wall_height = wall_height
        self.furniture_height = furniture_height
    
    def export(
        self,
        wall_mask: np.ndarray,
        door_mask: np.ndarray,
        window_mask: np.ndarray,
        furn_mask: np.ndarray,
        output_path: str
    ) -> Optional[str]:
        """
        Export 3D model to GLB file.
        
        Args:
            wall_mask: Wall segmentation mask (0-255 uint8)
            door_mask: Door segmentation mask
            window_mask: Window segmentation mask
            furn_mask: Furniture segmentation mask
            output_path: Output GLB file path
            
        Returns:
            Output path if successful, None otherwise
        """
        try:
            import trimesh
            from shapely.geometry import Polygon
            from skimage import measure
            
            logger.info("Generating 3D model...")
            
            # Convert masks to binary
            wall_mask = (wall_mask > 127).astype(np.uint8)
            door_mask = (door_mask > 127).astype(np.uint8)
            window_mask = (window_mask > 127).astype(np.uint8)
            furn_mask = (furn_mask > 127).astype(np.uint8)
            
            # Extract polygons from masks
            wall_polys = self._extract_polygons(wall_mask, min_area=200)
            door_polys = self._extract_polygons(door_mask, min_area=50)
            window_polys = self._extract_polygons(window_mask, min_area=50)
            furn_polys = self._extract_polygons(furn_mask, min_area=100)
            
            scene_meshes = []
            
            # Create wall meshes with openings
            for wall_poly in wall_polys:
                wall_mesh = self._create_wall_mesh(
                    wall_poly,
                    door_polys + window_polys,
                    door_polys
                )
                if wall_mesh is not None:
                    scene_meshes.append(wall_mesh)
            
            # Create furniture meshes
            for furn_poly in furn_polys:
                furn_mesh = self._create_furniture_mesh(furn_poly)
                if furn_mesh is not None:
                    scene_meshes.append(furn_mesh)
            
            if not scene_meshes:
                logger.warning("No meshes generated")
                return None
            
            # Combine into scene and export
            scene = trimesh.Scene(scene_meshes)
            scene.export(output_path)
            
            # Cleanup
            del scene_meshes, scene
            gc.collect()
            
            logger.info(f"Exported 3D model to: {output_path}")
            return output_path
            
        except ImportError as e:
            logger.error(f"Missing required library for 3D export: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to export 3D model: {e}")
            return None
    
    def _extract_polygons(
        self,
        mask: np.ndarray,
        min_area: float = 100.0
    ) -> list:
        """
        Extract polygons from binary mask.
        
        Args:
            mask: Binary mask
            min_area: Minimum polygon area
            
        Returns:
            List of Shapely Polygon objects
        """
        try:
            from shapely.geometry import Polygon
            from skimage import measure
            
            contours = measure.find_contours(mask, 0.5)
            polygons = []
            
            for contour in contours:
                try:
                    poly = Polygon(contour).simplify(2.0)
                    if poly.is_valid and poly.area > min_area:
                        polygons.append(poly)
                except Exception as e:
                    logger.debug(f"Invalid polygon: {e}")
                    continue
            
            return polygons
            
        except Exception as e:
            logger.error(f"Failed to extract polygons: {e}")
            return []
    
    def _create_wall_mesh(
        self,
        wall_poly,
        opening_polys: list,
        door_polys: list
    ):
        """
        Create wall mesh with door and window openings.
        
        Args:
            wall_poly: Wall polygon
            opening_polys: List of door and window polygons
            door_polys: List of door polygons (subset of opening_polys)
            
        Returns:
            Trimesh object or None
        """
        try:
            import trimesh
            
            # Extrude wall polygon
            wall_mesh = trimesh.creation.extrude_polygon(
                wall_poly,
                height=self.wall_height
            )
            
            # Boolean subtract openings
            for opening_poly in opening_polys:
                if not opening_poly.intersects(wall_poly):
                    continue
                
                if opening_poly.area < 1:
                    continue
                
                try:
                    # Determine opening height
                    if opening_poly in door_polys:
                        # Door: full height
                        opening_mesh = trimesh.creation.extrude_polygon(
                            opening_poly,
                            height=self.wall_height
                        )
                    else:
                        # Window: partial height, elevated
                        window_height = self.wall_height * 0.6
                        opening_mesh = trimesh.creation.extrude_polygon(
                            opening_poly,
                            height=window_height
                        )
                        # Elevate window
                        opening_mesh.apply_translation([0, 0, self.wall_height * 0.4])
                    
                    # Boolean difference
                    wall_mesh = wall_mesh.difference(opening_mesh)
                    
                except Exception as e:
                    logger.debug(f"Failed to subtract opening: {e}")
                    continue
            
            # Set wall color (white/light gray)
            wall_mesh.visual.face_colors = [240, 240, 240, 255]
            
            return wall_mesh
            
        except Exception as e:
            logger.debug(f"Failed to create wall mesh: {e}")
            return None
    
    def _create_furniture_mesh(self, furn_poly):
        """
        Create furniture mesh.
        
        Args:
            furn_poly: Furniture polygon
            
        Returns:
            Trimesh object or None
        """
        try:
            import trimesh
            
            # Extrude furniture (lower height)
            furn_mesh = trimesh.creation.extrude_polygon(
                furn_poly,
                height=self.furniture_height
            )
            
            # Set furniture color (blue-ish)
            furn_mesh.visual.face_colors = [100, 150, 250, 255]
            
            return furn_mesh
            
        except Exception as e:
            logger.debug(f"Failed to create furniture mesh: {e}")
            return None
