#!/usr/bin/env python3
"""
Gradio Web Interface for Floorplan2DXF Converter
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional, Tuple

import gradio as gr
import cv2
import numpy as np

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_app():
    """Initialize the application and load model."""
    try:
        from floorplan_processor import FloorplanProcessor
        from config_manager import ConfigManager
        
        # Setup directories
        work_dir = Path('./Floorplan2DXF_Output')
        work_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_dir = work_dir / 'checkpoints'
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Load config
        config_manager = ConfigManager(work_dir)
        config = config_manager.load_config()
        
        # Initialize processor
        processor = FloorplanProcessor(config, work_dir, checkpoint_dir)
        
        logger.info("Application initialized successfully")
        return processor, work_dir
        
    except Exception as e:
        logger.error(f"Failed to initialize application: {e}")
        raise


def process_floorplan(
    image: np.ndarray,
    processor,
    work_dir: Path
) -> Tuple[Optional[np.ndarray], Optional[str], Optional[str]]:
    """
    Process floor plan image.
    
    Args:
        image: Input image array (RGB)
        processor: FloorplanProcessor instance
        work_dir: Working directory
        
    Returns:
        Tuple of (visualization_image, dxf_path, glb_path)
    """
    if image is None:
        return None, None, None
    
    try:
        # Convert RGB to BGR for OpenCV
        img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Save temporary input file
        temp_input = work_dir / 'temp_input.png'
        cv2.imwrite(str(temp_input), img_bgr)
        
        # Process image
        success = processor.process_image(str(temp_input))
        
        if not success:
            logger.error("Processing failed")
            return None, None, None
        
        # Get output files
        output_dir = work_dir / 'output'
        vis_path = output_dir / 'temp_input_visualization.png'
        dxf_path = output_dir / 'temp_input.dxf'
        glb_path = output_dir / 'temp_input.glb'
        
        # Load visualization
        vis_img = None
        if vis_path.exists():
            vis_img = cv2.imread(str(vis_path))
            vis_img = cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB)
        
        # Return paths
        dxf_file = str(dxf_path) if dxf_path.exists() else None
        glb_file = str(glb_path) if glb_path.exists() else None
        
        return vis_img, dxf_file, glb_file
        
    except Exception as e:
        logger.error(f"Processing error: {e}")
        return None, None, None


def create_interface():
    """Create and configure Gradio interface."""
    
    # Initialize app
    try:
        processor, work_dir = initialize_app()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        # Create error interface
        with gr.Blocks() as demo:
            gr.Markdown("## ⚠️ Application Failed to Initialize")
            gr.Markdown(f"Error: {str(e)}")
            gr.Markdown("Please ensure all dependencies are installed: `pip install -r requirements.txt`")
        return demo
    
    # Create processing function with closure
    def process_wrapper(image):
        return process_floorplan(image, processor, work_dir)
    
    # Create interface
    with gr.Blocks(
        title="Floorplan to DXF/3D Converter",
        theme=gr.themes.Soft()
    ) as demo:
        gr.Markdown("# 🏗️ Floorplan to DXF/3D Converter")
        gr.Markdown(
            "Upload a floor plan image to convert it to DXF and 3D (GLB) formats. "
            "The model segments walls, doors, windows, and furniture."
        )
        
        with gr.Row():
            with gr.Column():
                input_image = gr.Image(
                    label="Input Floor Plan",
                    type="numpy",
                    height=400
                )
                process_btn = gr.Button(
                    "🚀 Process Floor Plan",
                    variant="primary",
                    size="lg"
                )
            
            with gr.Column():
                output_image = gr.Image(
                    label="Segmentation Visualization",
                    height=400
                )
        
        with gr.Row():
            dxf_output = gr.File(label="📐 Download DXF")
            glb_output = gr.File(label="🎨 Download 3D Model (GLB)")
        
        # Instructions
        with gr.Accordion("ℹ️ Instructions", open=False):
            gr.Markdown("""
            ### How to use:
            1. Upload a floor plan image (PNG, JPG, or JPEG)
            2. Click "Process Floor Plan" button
            3. Wait for processing to complete
            4. View the segmentation visualization
            5. Download DXF file for CAD software
            6. Download GLB file for 3D viewing
            
            ### Legend:
            - **Red**: Walls
            - **Green**: Doors
            - **Blue**: Windows
            - **Yellow**: Furniture
            
            ### Notes:
            - Processing may take 10-60 seconds depending on image size
            - For best results, use high-resolution images
            - The model works best with clean, architectural floor plans
            """)
        
        # Connect button
        process_btn.click(
            fn=process_wrapper,
            inputs=[input_image],
            outputs=[output_image, dxf_output, glb_output]
        )
    
    return demo


def main():
    """Main entry point for web interface."""
    try:
        demo = create_interface()
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            show_error=True
        )
    except Exception as e:
        logger.error(f"Failed to launch interface: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
