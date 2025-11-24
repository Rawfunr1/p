"""Model building and management."""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import torch
import torch.nn as nn
import torch.optim as optim

logger = logging.getLogger(__name__)


class ModelBuilder:
    """Builds and manages deep learning models."""
    
    def __init__(self, config: Dict[str, Any], checkpoint_dir: Path):
        """
        Initialize model builder.
        
        Args:
            config: Configuration dictionary
            checkpoint_dir: Directory for saving checkpoints
        """
        self.config = config
        self.checkpoint_dir = Path(checkpoint_dir)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
    
    def build_model(self, classes: List[str]) -> nn.Module:
        """
        Build segmentation model.
        
        Args:
            classes: List of class names
            
        Returns:
            PyTorch model
        """
        try:
            import segmentation_models_pytorch as smp
            
            model_type = self.config.get('model_type', 'deeplab')
            encoder = self.config.get('encoder', 'resnet34')
            
            if model_type == 'deeplab':
                model = smp.DeepLabV3Plus(
                    encoder_name=encoder,
                    encoder_weights='imagenet',
                    classes=len(classes),
                    activation='sigmoid'
                )
            elif model_type == 'unet':
                model = smp.Unet(
                    encoder_name=encoder,
                    encoder_weights='imagenet',
                    classes=len(classes),
                    activation='sigmoid'
                )
            else:
                raise ValueError(f"Unsupported model type: {model_type}")
            
            model = model.to(self.device)
            logger.info(f"Built {model_type} model with {encoder} encoder")
            return model
            
        except ImportError as e:
            logger.error(f"Failed to import segmentation_models_pytorch: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to build model: {e}")
            raise
    
    def save_checkpoint(
        self,
        model: nn.Module,
        optimizer: optim.Optimizer,
        epoch: int,
        loss: float,
        is_best: bool = False
    ) -> None:
        """
        Save model checkpoint.
        
        Args:
            model: Model to save
            optimizer: Optimizer state
            epoch: Current epoch
            loss: Current loss value
            is_best: Whether this is the best model so far
        """
        try:
            state = {
                'epoch': epoch,
                'model_state_dict': model.state_dict(),
                'optimizer_state_dict': optimizer.state_dict(),
                'loss': loss,
                'config': self.config
            }
            
            # Save regular checkpoint
            checkpoint_path = self.checkpoint_dir / f'checkpoint_epoch_{epoch}.pth'
            torch.save(state, checkpoint_path)
            logger.info(f"Saved checkpoint: {checkpoint_path}")
            
            # Save best model
            if is_best:
                best_path = self.checkpoint_dir / 'best_model.pth'
                torch.save(state, best_path)
                logger.info(f"Saved best model: {best_path}")
                
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(
        self,
        model: nn.Module,
        optimizer: Optional[optim.Optimizer] = None,
        checkpoint_path: Optional[Path] = None
    ) -> int:
        """
        Load model checkpoint.
        
        Args:
            model: Model to load weights into
            optimizer: Optional optimizer to load state into
            checkpoint_path: Path to checkpoint file (default: best_model.pth)
            
        Returns:
            Starting epoch number (0 if no checkpoint found)
        """
        if checkpoint_path is None:
            checkpoint_path = self.checkpoint_dir / 'best_model.pth'
        
        if not checkpoint_path.exists():
            logger.warning(f"No checkpoint found at {checkpoint_path}")
            return 0
        
        try:
            state = torch.load(checkpoint_path, map_location=self.device)
            
            # Handle both old and new checkpoint formats
            if 'model_state_dict' in state:
                model.load_state_dict(state['model_state_dict'])
                if optimizer is not None and 'optimizer_state_dict' in state:
                    optimizer.load_state_dict(state['optimizer_state_dict'])
                epoch = state.get('epoch', 0)
            else:
                # Old format - just state dict
                model.load_state_dict(state)
                epoch = 0
            
            logger.info(f"Loaded checkpoint from {checkpoint_path}")
            return epoch + 1
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return 0
    
    def get_optimizer(self, model: nn.Module) -> optim.Optimizer:
        """
        Create optimizer for model.
        
        Args:
            model: Model to optimize
            
        Returns:
            Optimizer instance
        """
        lr = self.config.get('learning_rate', 0.0004)
        optimizer = optim.Adam(model.parameters(), lr=lr)
        logger.info(f"Created Adam optimizer with lr={lr}")
        return optimizer
    
    @staticmethod
    def get_loss_function():
        """
        Get combined loss function (BCE + Dice).
        
        Returns:
            Loss calculation function
        """
        bce_loss = nn.BCELoss()
        
        def combined_loss(outputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
            """Calculate BCE + Dice loss."""
            bce = bce_loss(outputs, targets)
            
            # Dice loss
            intersection = (outputs * targets).sum()
            dice = 1 - (2 * intersection + 1e-6) / (
                outputs.sum() + targets.sum() + 1e-6
            )
            
            return bce + dice
        
        return combined_loss
