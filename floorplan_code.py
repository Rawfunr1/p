import os
import subprocess
import time
import requests
import textwrap

# ১. লাইব্রেরি ইনস্টল ফাংশন
def install_dependencies():
    print("⏳ লাইব্রেরি ইনস্টল হচ্ছে...")
    # sknw, trimesh, scipy সহ সমস্ত প্রয়োজনীয় লাইব্রেরি ইনস্টল করা হচ্ছে
    subprocess.check_call([
        "pip", "install", "-q", 
        "segmentation-models-pytorch", "easyocr", "networkx", "sknw", 
        "scikit-image", "torch", "albumentations", "tqdm", "matplotlib", "ezdxf", 
        "torchvision", "ultralytics", "trimesh", "shapely", 
        "mapbox_earcut", "opencv-contrib-python", "gradio", "requests", "scipy" 
    ])
    print("✅ সিস্টেম প্রস্তুত!")

# ২. মেইন কোড এবং অ্যাপ কোড রাইট করা
def create_files():
    print("📝 অ্যাডভান্সড কোড ফাইল তৈরি হচ্ছে...")
    
    # --- Main Logic Code (floorplan_final_fixed.py) ---
    # আপডেট: train_entity_advanced ফাংশনে ব্যাচ সাইজ ফিক্স করা হয়েছে
    main_code = textwrap.dedent(r"""
import os, cv2, torch, yaml, json, shutil, gc
import torch.nn as nn
import torch.optim as optim
import numpy as np
import signal, time
from pathlib import Path
from torchvision import transforms
from PIL import Image, ImageOps 
import ezdxf
from tqdm import tqdm
import psutil
from shapely.geometry import Polygon

# --- ADVANCED IMPORTS ---
try:
    import trimesh
    from skimage import measure, morphology
    import segmentation_models_pytorch as smp
    from torchvision.transforms import ToTensor
except ImportError:
    pass

POSSIBLE_DIRS = ['/kaggle/input/floorplan2dxf-advanced', './input', '.']
SSD_ZIP_DIR = next((d for d in POSSIBLE_DIRS if os.path.exists(d) and any(f.endswith('.zip') for f in os.listdir(d))), None)
WORK_DIR = '/kaggle/working/Floorplan2DXF_Advanced_PRO' if os.path.exists('/kaggle') else './Floorplan2DXF_Output'

if not os.path.exists(WORK_DIR): os.makedirs(WORK_DIR)
if SSD_ZIP_DIR:
    for item in os.listdir(SSD_ZIP_DIR):
        if item.endswith('.zip'): shutil.unpack_archive(os.path.join(SSD_ZIP_DIR, item), WORK_DIR)

os.chdir(WORK_DIR)
CONFIG_PATH = os.path.join(WORK_DIR, "floorplan_config.yaml")
config = {"model_type": "deeplab", "encoder": "resnet34", "tile_sz": 512, "batch_size": 1, "classes": ["wall","door","window","furn"], "train_images": [], "mask_folder": "masks", "max_epochs": 10, "learning_rate": 0.0004}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH,"r") as f: config = yaml.safe_load(f)

CHECKPOINT_DIR = os.path.join(WORK_DIR, 'checkpoints')
Path(CHECKPOINT_DIR).mkdir(parents=True, exist_ok=True)
BEST_MODEL_PATH = os.path.join(CHECKPOINT_DIR, 'best_model.pth')
config["mask_folder"] = os.path.join(WORK_DIR, "masks")
img_dir = os.path.join(WORK_DIR, "images")
if os.path.exists(img_dir) and not config.get("train_images"):
    config["train_images"] = [os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
config["dxf_out"] = os.path.join(WORK_DIR, "output_dxf", "output_ultra.dxf")

# --- POWER FEATURES ---

def clean_mask(mask):
    """Morphological Closing to fix gaps in walls"""
    kernel = np.ones((5,5), np.uint8)
    # ছোট ছিদ্র বন্ধ করা
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    # ছোট নয়েজ রিমুভ করা
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
    return opened

def snap_to_orthogonal(line_points, snap_angle=12):
    """Stronger snapping for CAD-like lines"""
    p1, p2 = line_points
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    angle_rad = np.arctan2(dy, dx)
    angle_deg = np.rad2deg(angle_rad) % 180
    if abs(angle_deg) < snap_angle or abs(angle_deg - 180) < snap_angle:
        return (p1[0], p1[1]), (p2[0], p1[1]) 
    elif abs(angle_deg - 90) < snap_angle:
        return (p1[0], p1[1]), (p1[0], p2[1]) 
    return p1, p2

def export_3d_model_ultra(wall_mask, door_mask, window_mask, furn_mask, output_name="model_3d.glb"):
    print("🏗️ 3D (GLB) তৈরি হচ্ছে...")
    
    # 1. Walls
    wall_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(wall_mask, 0.5) if Polygon(c).area > 200]
    door_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(door_mask, 0.5) if Polygon(c).area > 50]
    window_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(window_mask, 0.5) if Polygon(c).area > 50]
    
    scene_meshes = []
    height = 100

    # Wall Logic with Boolean
    for w_poly in wall_polys:
        try:
            w_mesh = trimesh.creation.extrude_polygon(w_poly, height=height)
            for opening_poly in door_polys + window_polys:
                if opening_poly.intersects(w_poly):
                    if opening_poly.area < 1: continue 
                    if opening_poly in door_polys:
                         opening_mesh = trimesh.creation.extrude_polygon(opening_poly, height=height)
                    else: # Window
                        window_base = trimesh.creation.extrude_polygon(opening_poly, height=height * 0.6) 
                        window_base.apply_translation([0, 0, height * 0.4])
                        opening_mesh = window_base
                    w_mesh = w_mesh.difference(opening_mesh)
            
            # কালার দেওয়া (White Walls)
            w_mesh.visual.face_colors = [240, 240, 240, 255]
            scene_meshes.append(w_mesh)
        except: pass
    
    # 2. Furniture (Simple Extrusion Blocks)
    furn_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(furn_mask, 0.5) if Polygon(c).area > 100]
    for f_poly in furn_polys:
        try:
            # ফার্নিচার নিচু হবে (যেমন বেড বা টেবিল)
            f_mesh = trimesh.creation.extrude_polygon(f_poly, height=30) 
            f_mesh.visual.face_colors = [100, 150, 250, 255] # Blueish
            scene_meshes.append(f_mesh)
        except: pass

    if not scene_meshes: return None
    
    # Combine everything into a Scene
    scene = trimesh.Scene(scene_meshes)
    save_path = os.path.join(WORK_DIR, output_name)
    
    # GLB Export (Modern Format) 
    scene.export(save_path) # Trimesh auto-detects .glb extension
    
    del scene_meshes, scene
    gc.collect()
    return save_path

def export_dxf_ultra(lines_by_class, all_masks, config):
    filepath = config["dxf_out"]
    doc = ezdxf.new()
    msp = doc.modelspace()
    
    # লেয়ার তৈরি
    doc.layers.new(name='WALL', dxfattribs={'color': 7}) # White
    doc.layers.new(name='DOOR', dxfattribs={'color': 3}) # Green
    doc.layers.new(name='WINDOW', dxfattribs={'color': 4}) # Cyan
    doc.layers.new(name='FURNITURE', dxfattribs={'color': 1}) # Red
    
    # ১. লাইন যুক্ত করা
    for cls, lines in lines_by_class.items():
        if cls == 'furn': continue # ফার্নিচার আলাদাভাবে হ্যান্ডেল হবে
        for p1_raw, p2_raw in lines:
            p1, p2 = snap_to_orthogonal((p1_raw, p2_raw), snap_angle=12)
            msp.add_line(p1, p2, dxfattribs={"layer": cls.upper()})
    
    # ২. ফার্নিচার বক্স হিসেবে অ্যাড করা
    if 'furn' in config['classes']:
        furn_mask = (all_masks[config['classes'].index('furn')] > 0.5).astype(np.uint8)
        contours, _ = cv2.findContours(furn_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) > 200:
                rect = cv2.minAreaRect(cnt)
                box_pts = cv2.boxPoints(rect)
                box_pts = np.int0(box_pts)
                # DXF Polyline হিসেবে ফার্নিচার অ্যাড করা
                msp.add_lwpolyline(box_pts, close=True, dxfattribs={"layer": "FURNITURE"})

    # ৩. রুম লেবেলিং
    if 'wall' in config['classes']:
        wall_mask = (all_masks[config['classes'].index('wall')] > 0.5).astype(np.uint8)
        room_mask = cv2.bitwise_not(wall_mask)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(room_mask, 8, cv2.CV_32S)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] > 500:
                cx, cy = centroids[i]
                label = f"ROOM {i}"
                msp.add_text(label, dxfattribs={"height": 12, "color": 2}).set_pos((cx, cy), align="CENTER")

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    doc.saveas(filepath)
    print(f"✅ DXF Exported: {filepath}")

# ... (Helper functions: get_model_pro, tile_image, stitch_mask, Dataset classes remain optimized) ...
def get_model_pro(config, classes):
    return smp.DeepLabV3Plus(encoder_name=config.get('encoder','resnet34'), encoder_weights='imagenet', classes=len(classes), activation='sigmoid')

def tile_image(img, tile_sz=512, overlap=32):
    h, w = img.shape[:2]
    tiles = []
    for y in range(0, h, tile_sz-overlap):
        for x in range(0, w, tile_sz-overlap):
            y2, x2 = min(y+tile_sz, h), min(x+tile_sz, w)
            tile = img[y:y2, x:x2]
            if tile.shape[0]<tile_sz or tile.shape[1]<tile_sz:
                tile = cv2.copyMakeBorder(tile, 0, tile_sz-tile.shape[0], 0, tile_sz-tile.shape[1], cv2.BORDER_CONSTANT, value=0)
            tiles.append(((x,y), tile))
    return tiles, (h, w, tile_sz, overlap)

def stitch_mask(tiles, info):
    h, w, tile_sz, overlap = info
    out_mask = np.zeros((h,w), dtype=np.float32)
    count = np.zeros((h,w), dtype=np.float32)
    for (x, y), tile_pred in tiles:
        h_cr, w_cr = min(tile_sz, h-y), min(tile_sz, w-x)
        out_mask[y:y+h_cr, x:x+w_cr] += tile_pred[:h_cr, :w_cr]
        count[y:y+h_cr, x:x+w_cr] += 1
    return np.divide(out_mask, count, out=np.zeros_like(out_mask), where=count!=0)

def get_advanced_augmentation():
    return transforms.Compose([transforms.ColorJitter(brightness=0.3, contrast=0.3), transforms.ToTensor()])

class FloorPlanTileDataset(torch.utils.data.Dataset):
    def __init__(self, image_paths, mask_folder, transform=None, classes=[], tile_sz=512):
        self.image_paths = image_paths
        self.mask_folder = mask_folder
        self.transform = transform
        self.classes = classes
        self.tile_sz = tile_sz
    def __len__(self): return len(self.image_paths)
    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        img = cv2.imread(img_path)
        if img is None: return torch.zeros((3,self.tile_sz,self.tile_sz)), torch.zeros((len(self.classes),self.tile_sz,self.tile_sz))
        tiles, _ = tile_image(img, self.tile_sz)
        all_imgs, all_masks = [], []
        loaded_masks = {}
        for c in self.classes:
            m_path = os.path.join(self.mask_folder, f"{os.path.basename(img_path).split('.')[0]}_{c}.png")
            loaded_masks[c] = cv2.imread(m_path, 0)
        for (x,y), tile in tiles:
            tile_tensor = self.transform(Image.fromarray(tile)) if self.transform else ToTensor()(Image.fromarray(tile))
            tile_masks = []
            for c in self.classes:
                mask = loaded_masks[c]
                if mask is not None:
                    h_m, w_m = mask.shape
                    y_end, x_end = min(y+self.tile_sz, h_m), min(x+self.tile_sz, w_m)
                    mask_crop = mask[y:y_end, x:x_end]
                    if mask_crop.shape[0]<self.tile_sz or mask_crop.shape[1]<self.tile_sz:
                        mask_crop = cv2.copyMakeBorder(mask_crop, 0, self.tile_sz-mask_crop.shape[0], 0, self.tile_sz-mask_crop.shape[1], cv2.BORDER_CONSTANT, value=0)
                    mask_tile = mask_crop
                else: mask_tile = np.zeros((self.tile_sz,self.tile_sz))
                tile_masks.append(torch.Tensor(mask_tile/255.0))
            all_imgs.append(tile_tensor)
            all_masks.append(torch.stack(tile_masks))
        return torch.stack(all_imgs), torch.stack(all_masks)

def save_quantum_state(model, optimizer, epoch, loss, best_so_far=False):
    state = {'epoch': epoch, 'model_state_dict': model.state_dict(), 'optimizer_state_dict': optimizer.state_dict(), 'loss': loss}
    torch.save(state, os.path.join(CHECKPOINT_DIR, f'floorplan_ckpt_{epoch}.pth'))
    if best_so_far: torch.save(state, BEST_MODEL_PATH)

def load_latest_quantum_state(model, optimizer):
    if os.path.exists(BEST_MODEL_PATH):
        try:
            state = torch.load(BEST_MODEL_PATH)
            model.load_state_dict(state['model_state_dict'] if 'model_state_dict' in state else state)
            return state.get('epoch', 0) + 1
        except: pass
    return 0

def train_entity_advanced(config):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if not config.get("train_images"): 
        print("⚠️ কোনো ট্রেনিং ইমেজ নেই, স্কিপ করা হচ্ছে...")
        return
    model = get_model_pro(config, config["classes"]).to(device)
    dataset = FloorPlanTileDataset(config["train_images"], config["mask_folder"], get_advanced_augmentation(), config["classes"], config["tile_sz"])
    loader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=True, num_workers=2)
    optimizer = optim.Adam(model.parameters(), lr=config.get("learning_rate",0.0004))
    start_epoch = load_latest_quantum_state(model, optimizer)
    
    for epoch in range(start_epoch, config["max_epochs"]):
        model.train()
        total_loss = 0
        pbar = tqdm(loader, desc=f"Epoch {epoch}")
        for img_tiles, mask_tiles in pbar:
            images = img_tiles.view(-1, *img_tiles.shape[2:]).to(device)
            masks = mask_tiles.view(-1, *mask_tiles.shape[2:]).to(device)
            
            # --- FIX: BatchNorm Error prevent korar jonno ---
            if images.shape[0] == 1:
                images = torch.cat((images, images), dim=0)
                masks = torch.cat((masks, masks), dim=0)
            # -----------------------------------------------

            optimizer.zero_grad()
            outputs = model(images)
            bce = nn.BCELoss()(outputs, masks)
            dice = 1 - (2*(outputs*masks).sum() / ((outputs+masks).sum() + 1e-6))
            loss = bce + dice
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
            pbar.set_postfix({"loss": loss.item()})
        avg_loss = total_loss/len(loader)
        save_quantum_state(model, optimizer, epoch, avg_loss, best_so_far=True)

def predict_and_export_ultra(model, image_path, config):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    img = cv2.imread(image_path)
    if img is None: return
    tiles, info = tile_image(img, config.get("tile_sz",512))
    seg_full = []
    model.eval()
    with torch.no_grad():
        for (x,y), tile in tiles:
            img_tensor = transforms.ToTensor()(Image.fromarray(tile)).unsqueeze(0).to(device)
            seg = model(img_tensor)[0].cpu().numpy()
            seg_full.append(((x,y), seg))
    masks_stitched = [stitch_mask([(coord, seg_pred[i]) for coord, seg_pred in seg_full], info) for i in range(len(config["classes"]))]
    
    # Clean Masks (Noise Reduction)
    masks_clean = [clean_mask((m*255).astype(np.uint8)) for m in masks_stitched]
    
    try:
        wall_mask = (masks_clean[config['classes'].index('wall')] > 127).astype(np.uint8)
        door_mask = (masks_clean[config['classes'].index('door')] > 127).astype(np.uint8)
        window_mask = (masks_clean[config['classes'].index('window')] > 127).astype(np.uint8)
        furn_mask = (masks_clean[config['classes'].index('furn')] > 127).astype(np.uint8)
        
        # GLB Export
        export_3d_model_ultra(wall_mask, door_mask, window_mask, furn_mask, output_name="floorplan_3d.glb")
    except Exception as e: 
        print(f"⚠️ 3D Export Error: {e}")

    lines_by_class = {k: [] for k in config["classes"]}
    for idx, key in enumerate(lines_by_class.keys()):
        mask = masks_clean[idx]
        try:
            fld = cv2.ximgproc.createFastLineDetector(length_threshold=20)
            lines = fld.detect(mask)
            if lines is not None: lines_by_class[key] = [((l[0][0], l[0][1]), (l[0][2], l[0][3])) for l in lines]
        except:
            lines = cv2.HoughLinesP(cv2.Canny(mask, 30, 110), 1, np.pi/180, 50, minLineLength=30, maxLineGap=10)
            if lines is not None: lines_by_class[key] = [((l[0][0], l[0][1]), (l[0][2], l[0][3])) for l in lines]
            
    # DXF with Furniture Blocks
    export_dxf_ultra(lines_by_class, masks_stitched, config)
    gc.collect()
    torch.cuda.empty_cache()
    print("🧹 Memory Cleaned")

if __name__ == "__main__":
    train_entity_advanced(config)
    classes = config.get("classes",["wall","door","window","furn"])
    model = get_model_pro(config, classes).to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    if os.path.exists(BEST_MODEL_PATH):
        try:
            state = torch.load(BEST_MODEL_PATH)
            model.load_state_dict(state['model_state_dict'] if 'model_state_dict' in state else state)
        except: pass
    if config.get("train_images"):
        predict_and_export_ultra(model, config["train_images"][0], config)
"""
    with open("floorplan_final_fixed.py", "w") as f:
        f.write(main_code)
        
    # --- UI Code (App.py) Updated for GLB ---
    app_code = textwrap.dedent(r"""
import gradio as gr
import os, cv2, torch, yaml, numpy as np
import segmentation_models_pytorch as smp
from torchvision import transforms
from PIL import Image
import trimesh
from shapely.geometry import Polygon
from skimage import measure, morphology
import ezdxf
import psutil
import gc

WORK_DIR = '/kaggle/working/Floorplan2DXF_Advanced_PRO' if os.path.exists('/kaggle') else './Floorplan2DXF_Output'
CHECKPOINT_DIR = os.path.join(WORK_DIR, 'checkpoints')
BEST_MODEL_PATH = os.path.join(CHECKPOINT_DIR, 'best_model.pth')
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# --- UI HELPER FUNCTIONS ---
def get_model(classes):
    return smp.DeepLabV3Plus(encoder_name="resnet34", encoder_weights=None, classes=len(classes), activation='sigmoid')

def tile_image(img, tile_sz=512, overlap=32):
    h, w = img.shape[:2]
    tiles = []
    for y in range(0, h, tile_sz-overlap):
        for x in range(0, w, tile_sz-overlap):
            y2, x2 = min(y+tile_sz, h), min(x+tile_sz, w)
            tile = img[y:y2, x:x2]
            if tile.shape[0]<tile_sz or tile.shape[1]<tile_sz:
                tile = cv2.copyMakeBorder(tile, 0, tile_sz-tile.shape[0], 0, tile_sz-tile.shape[1], cv2.BORDER_CONSTANT, value=0)
            tiles.append(((x,y), tile))
    return tiles, (h, w, tile_sz, overlap)

def stitch_mask(tiles, info):
    h, w, tile_sz, overlap = info
    out_mask = np.zeros((h,w), dtype=np.float32)
    count = np.zeros((h,w), dtype=np.float32)
    for (x, y), tile_pred in tiles:
        h_cr, w_cr = min(tile_sz, h-y), min(tile_sz, w-x)
        out_mask[y:y+h_cr, x:x+w_cr] += tile_pred[:h_cr, :w_cr]
        count[y:y+h_cr, x:x+w_cr] += 1
    return np.divide(out_mask, count, out=np.zeros_like(out_mask), where=count!=0)

def clean_mask(mask):
    kernel = np.ones((5,5), np.uint8)
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel)
    return opened

def snap_to_orthogonal(line_points, snap_angle=12):
    p1, p2 = line_points
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    angle_rad = np.arctan2(dy, dx)
    angle_deg = np.rad2deg(angle_rad) % 180
    if abs(angle_deg) < snap_angle or abs(angle_deg - 180) < snap_angle:
        return (p1[0], p1[1]), (p2[0], p1[1]) 
    elif abs(angle_deg - 90) < snap_angle:
        return (p1[0], p1[1]), (p1[0], p2[1]) 
    return p1, p2

def detect_and_label_rooms(wall_mask, msp):
    room_mask = cv2.bitwise_not(wall_mask)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(room_mask, 8, cv2.CV_32S)
    for i in range(1, num_labels):
        if stats[i, cv2.CC_STAT_AREA] > 500:
            cx, cy = centroids[i]
            label = f"ROOM {i}"
            msp.add_text(label, dxfattribs={"height": 10, "color": 2}).set_pos((cx, cy), align="CENTER")

def generate_3d_obj_ultra(wall_mask, door_mask, window_mask, furn_mask, output_path):
    # Same logic as main file but for web
    wall_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(wall_mask, 0.5) if Polygon(c).area > 200]
    door_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(door_mask, 0.5) if Polygon(c).area > 50]
    window_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(window_mask, 0.5) if Polygon(c).area > 50]
    scene_meshes = []
    height = 100
    for w_poly in wall_polys:
        try:
            w_mesh = trimesh.creation.extrude_polygon(w_poly, height=height)
            for opening_poly in door_polys + window_polys:
                if opening_poly.intersects(w_poly):
                    if opening_poly.area < 1: continue
                    if opening_poly in door_polys:
                         opening_mesh = trimesh.creation.extrude_polygon(opening_poly, height=height)
                    else:
                        window_base = trimesh.creation.extrude_polygon(opening_poly, height=height * 0.6) 
                        window_base.apply_translation([0, 0, height * 0.4])
                        opening_mesh = window_base
                    w_mesh = w_mesh.difference(opening_mesh)
            w_mesh.visual.face_colors = [240, 240, 240, 255]
            scene_meshes.append(w_mesh)
        except: pass
    
    furn_polys = [Polygon(c).simplify(2.0) for c in measure.find_contours(furn_mask, 0.5) if Polygon(c).area > 100]
    for f_poly in furn_polys:
        try:
            f_mesh = trimesh.creation.extrude_polygon(f_poly, height=30) 
            f_mesh.visual.face_colors = [100, 150, 250, 255] 
            scene_meshes.append(f_mesh)
        except: pass

    if not scene_meshes: return None
    scene = trimesh.Scene(scene_meshes)
    scene.export(output_path)
    return output_path

def generate_dxf_ultra(masks, classes, output_path):
    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.layers.new(name='WALL', dxfattribs={'color': 7})
    doc.layers.new(name='FURNITURE', dxfattribs={'color': 1})
    
    for idx, cls in enumerate(classes):
        if cls == 'furn': continue
        mask = masks[idx]
        try:
            fld = cv2.ximgproc.createFastLineDetector(length_threshold=20)
            lines = fld.detect(mask)
            if lines is not None: 
                for l in lines:
                    p1, p2 = snap_to_orthogonal(((l[0][0], l[0][1]), (l[0][2], l[0][3])), snap_angle=12)
                    msp.add_line(p1, p2, dxfattribs={"layer": cls.upper()})
        except: pass

    if 'furn' in classes:
        furn_mask = masks[classes.index('furn')]
        contours, _ = cv2.findContours(furn_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            if cv2.contourArea(cnt) > 200:
                rect = cv2.minAreaRect(cnt)
                box_pts = np.int0(cv2.boxPoints(rect))
                msp.add_lwpolyline(box_pts, close=True, dxfattribs={"layer": "FURNITURE"})

    if 'wall' in classes:
        wall_mask = masks[classes.index('wall')]
        detect_and_label_rooms(wall_mask, msp)
        
    doc.saveas(output_path)
    return output_path

classes = ["wall","door","window","furn"]
model = get_model(classes).to(DEVICE)
if os.path.exists(BEST_MODEL_PATH):
    try:
        state = torch.load(BEST_MODEL_PATH, map_location=DEVICE)
        model.load_state_dict(state['model_state_dict'] if 'model_state_dict' in state else state)
        print("✅ মডেল লোড হয়েছে।")
    except Exception as e: print(f"⚠️ মডেল লোড এরর: {e}")
else: print("⚠️ মডেল নেই, র‍্যান্ডম ওয়েট।")

def predict_floorplan(image):
    if image is None: return None, None, None, None
    img_cv = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    tiles, info = tile_image(img_cv, tile_sz=512)
    model.eval()
    seg_full = []
    with torch.no_grad():
        for (x,y), tile in tiles:
            img_tensor = transforms.ToTensor()(Image.fromarray(tile)).unsqueeze(0).to(DEVICE)
            seg = model(img_tensor)[0].cpu().numpy()
            seg_full.append(((x,y), seg))
    masks_stitched = [stitch_mask([(coord, seg_pred[i]) for coord, seg_pred in seg_full], info) for i in range(len(classes))]
    
    # Clean up
    masks_clean = [clean_mask((m*255).astype(np.uint8)) for m in masks_stitched]
    
    out_dir = os.path.join(WORK_DIR, "web_output")
    os.makedirs(out_dir, exist_ok=True)
    
    wall_mask = (masks_clean[classes.index('wall')] > 127).astype(np.uint8)
    door_mask = (masks_clean[classes.index('door')] > 127).astype(np.uint8)
    window_mask = (masks_clean[classes.index('window')] > 127).astype(np.uint8)
    furn_mask = (masks_clean[classes.index('furn')] > 127).astype(np.uint8)
    
    obj_path = os.path.join(out_dir, "model_3d.glb")
    generate_3d_obj_ultra(wall_mask, door_mask, window_mask, furn_mask, obj_path)
    
    dxf_path = os.path.join(out_dir, "plan.dxf")
    generate_dxf_ultra(masks_clean, classes, dxf_path)
    
    overlay = img_cv.copy()
    colors = [(0,0,255), (0,255,0), (255,0,0), (0,255,255)] 
    for idx, mask in enumerate(masks_clean):
        color_mask = np.zeros_like(img_cv)
        color_mask[:] = colors[idx]
        overlay = np.where(mask[..., None] > 127, cv2.addWeighted(overlay, 0.7, color_mask, 0.3, 0), overlay)
    overlay_rgb = cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB)
    
    del seg_full, masks_stitched, masks_clean, img_cv, wall_mask
    gc.collect()
    torch.cuda.empty_cache()
    
    return overlay_rgb, obj_path, dxf_path, obj_path

custom_css = "#component-0 {max_width: 800px; margin: auto;}"
with gr.Blocks(css=custom_css, title="Floorplan Ultra") as demo:
    gr.Markdown("# 🏗️ Floorplan2DXF Ultra Interface")
    gr.Markdown("New Features: **GLB Export**, **Furniture Blocks**, **Clean Lines**")
    with gr.Row():
        with gr.Column():
            input_img = gr.Image(label="Input", type="numpy")
            btn = gr.Button("🚀 Generate Ultra Model", variant="primary")
        with gr.Column():
            output_img = gr.Image(label="Clean Overlay")
    with gr.Row():
        model_3d = gr.Model3D(label="3D Viewer (GLB)", clear_color=[0.8, 0.8, 0.8, 1.0])
        file_dxf = gr.File(label="Download DXF")
        file_obj = gr.File(label="Download GLB")
    btn.click(predict_floorplan, inputs=input_img, outputs=[output_img, model_3d, file_dxf, file_obj])

print("🌐 Interface launch হচ্ছে...")
demo.launch(share=True, debug=True)
""")
    with open("app.py", "w") as f:
        f.write(app_code)
    print("✅ ফাইল তৈরি সম্পন্ন!")

# ৩. স্যাম্পল ডেটা এবং ফোল্ডার তৈরি
def setup_folders_and_data():
    print("📂 ফোল্ডার স্ট্রাকচার তৈরি হচ্ছে...")
    base_dir = '/kaggle/working/Floorplan2DXF_Advanced_PRO' if os.path.exists('/kaggle') else './Floorplan2DXF_Output'
    os.makedirs(os.path.join(base_dir, "images"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "masks"), exist_ok=True)
    
    img_url = "https://raw.githubusercontent.com/art-programmer/FloorplanTransformation/master/TestData/1.png"
    sample_img_path = os.path.join(base_dir, "images", "sample_plan.png")
    try:
        if not os.path.exists(sample_img_path):
            r = requests.get(img_url, allow_redirects=True)
            open(sample_img_path, 'wb').write(r.content)
            print("✅ স্যাম্পল ইমেজ ডাউনলোড হয়েছে")
    except Exception as e:
        print(f"⚠️ ইমেজ সমস্যা: {e}")

if __name__ == "__main__":
    install_dependencies()
    create_files()
    setup_folders_and_data()
    print("\n🚀 প্রসেসিং এবং ইন্টারফেস চালু হচ্ছে...")
    subprocess.run(["python", "floorplan_final_fixed.py"])
    print("\n🌐 Gradio UI চালু হচ্ছে...")
    subprocess.run(["python", "app.py"])