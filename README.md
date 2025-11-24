# Floorplan to DXF/3D Converter

A complete refactored and optimized solution for converting floor plan images to DXF and 3D (GLB) formats using deep learning.

## Features

- ✅ **Semantic Segmentation**: Detects walls, doors, windows, and furniture
- ✅ **DXF Export**: CAD-compatible format with proper layers and room labels
- ✅ **3D Model Export**: GLB format with realistic walls and furniture
- ✅ **Web Interface**: Easy-to-use Gradio-based UI
- ✅ **Batch Processing**: Process multiple images efficiently
- ✅ **Memory Optimized**: Proper memory management and cleanup
- ✅ **Error Handling**: Robust error handling throughout

## Installation

### Prerequisites

- Python 3.8 or higher
- CUDA-capable GPU (optional, but recommended for training)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/Rawfunr1/p.git
cd p
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Command Line Interface

Process floor plans from the command line:

```bash
python floorplan_main.py
```

This will:
- Setup the working environment
- Load or create configuration
- Train the model (if training images are available)
- Process images in the `images` folder

### Web Interface

Launch the interactive web interface:

```bash
python app.py
```

Then open your browser to `http://localhost:7860`

### Python API

Use the processor directly in your code:

```python
from pathlib import Path
from floorplan_processor import FloorplanProcessor
from config_manager import ConfigManager

# Setup
work_dir = Path('./output')
checkpoint_dir = work_dir / 'checkpoints'

# Load config
config_manager = ConfigManager(work_dir)
config = config_manager.load_config()

# Initialize processor
processor = FloorplanProcessor(config, work_dir, checkpoint_dir)

# Process an image
processor.process_image('path/to/floorplan.png')
```

## Configuration

Edit `floorplan_config.yaml` to customize:

```yaml
model_type: deeplab      # Model architecture (deeplab, unet)
encoder: resnet34        # Encoder backbone
tile_sz: 512             # Tile size for processing
batch_size: 2            # Batch size for training
classes:                 # Classes to segment
  - wall
  - door
  - window
  - furn
max_epochs: 10           # Training epochs
learning_rate: 0.0004    # Learning rate
```

## Project Structure

```
.
├── floorplan_main.py          # Main entry point
├── app.py                     # Web interface
├── config_manager.py          # Configuration management
├── model_builder.py           # Model building and training
├── floorplan_processor.py     # Main processing logic
├── dataset.py                 # Dataset classes
├── image_utils.py             # Image processing utilities
├── dxf_exporter.py            # DXF export functionality
├── model_3d_exporter.py       # 3D model export
├── requirements.txt           # Dependencies
└── README.md                  # This file
```

## Training

To train on your own data:

1. Organize your data:
```
Floorplan2DXF_Output/
├── images/
│   ├── plan1.png
│   └── plan2.png
└── masks/
    ├── plan1_wall.png
    ├── plan1_door.png
    ├── plan1_window.png
    ├── plan1_furn.png
    ├── plan2_wall.png
    └── ...
```

2. Run training:
```bash
python floorplan_main.py
```

## Performance Optimizations

This refactored version includes:

- **Proper module structure**: Separated concerns into logical modules
- **Type hints**: Better code clarity and IDE support
- **Error handling**: Comprehensive try-catch blocks
- **Memory management**: Proper cleanup and garbage collection
- **Efficient tiling**: Optimized image tiling and stitching
- **Batch normalization fix**: Handles edge cases in training
- **Context managers**: Proper resource management
- **Logging**: Detailed logging throughout

## Fixed Issues

✅ **Syntax Errors**: Fixed unclosed parentheses and string formatting
✅ **Code Structure**: Refactored from nested strings to proper modules
✅ **Error Handling**: Added comprehensive error handling
✅ **Type Safety**: Added type hints throughout
✅ **Performance**: Optimized memory usage and processing
✅ **Security**: Removed command injection risks
✅ **Documentation**: Added comprehensive documentation
✅ **Code Quality**: Improved formatting and readability

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Support

For issues and questions, please open an issue on GitHub.