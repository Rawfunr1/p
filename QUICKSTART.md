# Quick Start Guide

Get up and running with Floorplan2DXF in minutes!

## Prerequisites

- Python 3.8 or higher
- pip package manager
- (Optional) CUDA-capable GPU for faster processing

## Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/Rawfunr1/p.git
cd p
```

### Step 2: Create Virtual Environment (Recommended)
```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

This will install all required packages including:
- PyTorch and torchvision
- OpenCV
- Segmentation models
- Trimesh for 3D export
- Gradio for web interface
- And more...

**Note**: Installation may take 5-10 minutes depending on your internet connection.

## Usage

### Option 1: Web Interface (Easiest)

Launch the interactive web interface:
```bash
python app.py
```

Then open your browser to: `http://localhost:7860`

**Steps**:
1. Upload a floor plan image
2. Click "Process Floor Plan"
3. Wait for processing (10-60 seconds)
4. Download DXF and/or GLB files

### Option 2: Command Line

Process floor plans from the command line:

```bash
# 1. Create directories
mkdir -p Floorplan2DXF_Output/images
mkdir -p Floorplan2DXF_Output/masks

# 2. Add your floor plan images to the images folder
cp /path/to/your/floorplan.png Floorplan2DXF_Output/images/

# 3. Run processing
python floorplan_main.py
```

Output files will be in: `Floorplan2DXF_Output/output/`

### Option 3: Python API

Use in your own Python code:

```python
from pathlib import Path
from floorplan_processor import FloorplanProcessor
from config_manager import ConfigManager

# Setup
work_dir = Path('./output')
checkpoint_dir = work_dir / 'checkpoints'
work_dir.mkdir(parents=True, exist_ok=True)
checkpoint_dir.mkdir(parents=True, exist_ok=True)

# Initialize
config_manager = ConfigManager(work_dir)
config = config_manager.load_config()
processor = FloorplanProcessor(config, work_dir, checkpoint_dir)

# Process an image
processor.process_image('path/to/floorplan.png')
```

## Training Your Own Model

If you have labeled training data:

### Step 1: Organize Your Data

```
Floorplan2DXF_Output/
├── images/
│   ├── plan1.png
│   ├── plan2.png
│   └── ...
└── masks/
    ├── plan1_wall.png      # Wall mask for plan1
    ├── plan1_door.png      # Door mask for plan1
    ├── plan1_window.png    # Window mask for plan1
    ├── plan1_furn.png      # Furniture mask for plan1
    ├── plan2_wall.png
    └── ...
```

**Mask Format**:
- Binary images (0 = background, 255 = object)
- Same dimensions as input image
- PNG format

### Step 2: Configure Training

Edit `Floorplan2DXF_Output/floorplan_config.yaml`:

```yaml
max_epochs: 20              # Number of training epochs
learning_rate: 0.0004       # Learning rate
batch_size: 2               # Batch size (adjust based on GPU memory)
tile_sz: 512                # Tile size for processing
```

### Step 3: Run Training

```bash
python floorplan_main.py
```

Training will:
- Load your images and masks
- Train the segmentation model
- Save checkpoints to `checkpoints/`
- Save best model as `checkpoints/best_model.pth`

## Common Issues

### Issue: "No module named 'torch'"
**Solution**: Install dependencies: `pip install -r requirements.txt`

### Issue: "CUDA out of memory"
**Solution**: 
- Reduce batch_size in config
- Use CPU instead: Set `CUDA_VISIBLE_DEVICES=""`
- Reduce tile_sz to 256 or 384

### Issue: "No training images found"
**Solution**: 
- Check that images are in `Floorplan2DXF_Output/images/`
- Supported formats: PNG, JPG, JPEG

### Issue: Web interface won't start
**Solution**:
- Check port 7860 is available
- Try different port: Edit app.py and change `server_port=7860`

## Example Workflow

Here's a complete example workflow:

```bash
# 1. Setup
git clone https://github.com/Rawfunr1/p.git
cd p
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Download sample image (or use your own)
mkdir -p Floorplan2DXF_Output/images
wget https://example.com/sample_floorplan.png -O Floorplan2DXF_Output/images/sample.png

# 3. Process
python floorplan_main.py

# 4. Check results
ls Floorplan2DXF_Output/output/
# sample.dxf - CAD file
# sample.glb - 3D model
# sample_visualization.png - Preview
```

## Output Formats

### DXF File
- CAD-compatible format
- Separate layers for walls, doors, windows, furniture
- Room labels
- Open with: AutoCAD, LibreCAD, QCAD, DraftSight

### GLB File
- 3D model format
- Realistic wall heights
- Door and window openings
- Furniture blocks
- Open with: Blender, 3D Viewer, Sketchfab

### Visualization
- PNG image showing segmentation overlay
- Color-coded by class
- Useful for quality checking

## Tips for Best Results

1. **Image Quality**: Use high-resolution images (min 1024x1024)
2. **Clean Images**: Remove noise, ensure good contrast
3. **Training Data**: More training images = better results
4. **GPU**: Use GPU for 5-10x faster processing
5. **Batch Size**: Adjust based on GPU memory (2-8 typical)

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [IMPROVEMENTS.md](IMPROVEMENTS.md) for technical details
- Customize configuration in `floorplan_config.yaml`
- Train on your own data for domain-specific results

## Getting Help

- Check the [README.md](README.md) for more information
- Open an issue on GitHub for bugs
- Review logs in console output for error details

## License

MIT License - See LICENSE file for details
