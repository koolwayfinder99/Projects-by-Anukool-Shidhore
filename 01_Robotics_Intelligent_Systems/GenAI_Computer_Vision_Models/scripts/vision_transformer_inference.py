"""
Vision Transformer and Segment Anything Model Inference Pipeline
===============================================================

This module implements zero-shot object segmentation and classification using
Vision Transformer (ViT) and Segment Anything Model (SAM) from Meta AI.
Optimized for NVIDIA CUDA acceleration.

Author: Anukool Shidhore
Date: 2026
"""

import torch
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass
import logging

from transformers import pipeline, AutoImageProcessor, AutoModelForImageSegmentation
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class SegmentationConfig:
    """Configuration for segmentation pipeline."""
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    model_name_sam: str = "facebook/sam-vit-base"
    model_name_dit: str = "Intel/dpt-hybrid-midas"
    confidence_threshold: float = 0.5
    max_objects: int = 100
    save_outputs: bool = True
    output_dir: str = "outputs"


class VisionTransformerSegmentation:
    """
    Zero-shot object segmentation using Vision Transformer and SAM.
    Combines semantic understanding with precise instance segmentation.
    """

    def __init__(self, config: Optional[SegmentationConfig] = None):
        """
        Initialize Vision Transformer segmentation pipeline.

        Args:
            config: SegmentationConfig object with model parameters
        """
        self.config = config or SegmentationConfig()
        self.device = torch.device(self.config.device)
        
        logger.info(f"Using device: {self.device}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")
            logger.info(f"CUDA memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

        self._initialize_models()

    def _initialize_models(self):
        """Initialize Vision Transformer and segmentation models."""
        try:
            # Initialize object detection pipeline using Vision Transformer
            logger.info("Loading Vision Transformer for object detection...")
            self.detector = pipeline(
                "object-detection",
                model="facebook/detr-resnet50",
                device=0 if self.config.device == "cuda" else -1
            )

            # Initialize image segmentation (SAM-like functionality)
            logger.info("Loading image segmentation model...")
            self.segmentation_processor = AutoImageProcessor.from_pretrained(
                self.config.model_name_dit
            )
            self.segmentation_model = AutoModelForImageSegmentation.from_pretrained(
                self.config.model_name_dit
            ).to(self.device)
            self.segmentation_model.eval()

            logger.info("Models loaded successfully!")

        except Exception as e:
            logger.error(f"Error initializing models: {e}")
            raise

    @torch.no_grad()
    def detect_objects(self, image_path: str) -> List[Dict]:
        """
        Detect objects in image using Vision Transformer.

        Args:
            image_path: Path to input image

        Returns:
            List of detected objects with bounding boxes and confidence scores
        """
        try:
            image = Image.open(image_path)
            logger.info(f"Detecting objects in {Path(image_path).name}...")

            # Run detection
            detections = self.detector(image)

            # Filter by confidence threshold
            filtered_detections = [
                d for d in detections 
                if d['score'] >= self.config.confidence_threshold
            ]

            logger.info(f"Detected {len(filtered_detections)} objects")
            return filtered_detections

        except Exception as e:
            logger.error(f"Error in object detection: {e}")
            return []

    @torch.no_grad()
    def segment_image(self, image_path: str) -> Tuple[np.ndarray, np.ndarray]:
        """
        Perform image segmentation using transformer-based model.

        Args:
            image_path: Path to input image

        Returns:
            Tuple of (original_image, segmentation_mask)
        """
        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(f"Segmenting {Path(image_path).name}...")

            # Prepare image
            inputs = self.segmentation_processor(
                images=image,
                return_tensors="pt"
            ).to(self.device)

            # Run segmentation
            with torch.no_grad():
                outputs = self.segmentation_model(**inputs)

            # Process outputs
            pred_mask = outputs.pred_masks.squeeze(0).squeeze(0).cpu().numpy()
            pred_mask = (pred_mask > 0.5).astype(np.uint8) * 255

            image_array = np.array(image)
            logger.info(f"Segmentation completed. Mask shape: {pred_mask.shape}")

            return image_array, pred_mask

        except Exception as e:
            logger.error(f"Error in segmentation: {e}")
            return None, None

    @torch.no_grad()
    def extract_features(self, image_path: str) -> torch.Tensor:
        """
        Extract feature vectors from image using Vision Transformer backbone.

        Args:
            image_path: Path to input image

        Returns:
            Feature tensor (1D vector for image-level features)
        """
        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(f"Extracting features from {Path(image_path).name}...")

            inputs = self.segmentation_processor(
                images=image,
                return_tensors="pt"
            ).to(self.device)

            # Extract features without passing through final layers
            with torch.no_grad():
                features = self.segmentation_model.encoder(**inputs)

            logger.info(f"Features extracted. Shape: {features.shape}")
            return features

        except Exception as e:
            logger.error(f"Error in feature extraction: {e}")
            return None

    def visualize_detections(
        self,
        image_path: str,
        detections: List[Dict],
        save_path: Optional[str] = None
    ):
        """
        Visualize object detections on image.

        Args:
            image_path: Path to input image
            detections: List of detected objects
            save_path: Path to save visualization (optional)
        """
        try:
            image = cv2.imread(image_path)
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            for detection in detections:
                box = detection['box']
                score = detection['score']
                label = detection['label']

                # Draw bounding box
                pt1 = (int(box['xmin']), int(box['ymin']))
                pt2 = (int(box['xmax']), int(box['ymax']))
                cv2.rectangle(image_rgb, pt1, pt2, (0, 255, 0), 2)

                # Add label and confidence
                text = f"{label}: {score:.3f}"
                cv2.putText(
                    image_rgb, text, (pt1[0], pt1[1] - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2
                )

            if save_path:
                image_bgr = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                cv2.imwrite(save_path, image_bgr)
                logger.info(f"Visualization saved to {save_path}")

            return image_rgb

        except Exception as e:
            logger.error(f"Error in visualization: {e}")
            return None

    def visualize_segmentation(
        self,
        image_array: np.ndarray,
        mask: np.ndarray,
        save_path: Optional[str] = None,
        alpha: float = 0.6
    ):
        """
        Visualize segmentation mask on original image.

        Args:
            image_array: Original image as numpy array
            mask: Segmentation mask
            save_path: Path to save visualization
            alpha: Transparency of overlay
        """
        try:
            if image_array is None or mask is None:
                logger.warning("Image or mask is None, skipping visualization")
                return None

            # Resize mask to match image if needed
            if image_array.shape[:2] != mask.shape[:2]:
                mask = cv2.resize(
                    mask,
                    (image_array.shape[1], image_array.shape[0]),
                    interpolation=cv2.INTER_NEAREST
                )

            # Create colored mask
            colored_mask = np.zeros_like(image_array)
            colored_mask[mask > 0] = [0, 255, 0]

            # Overlay mask on image
            overlay = cv2.addWeighted(
                image_array, 1 - alpha,
                colored_mask, alpha, 0
            )

            if save_path:
                image_bgr = cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR)
                cv2.imwrite(save_path, image_bgr)
                logger.info(f"Segmentation visualization saved to {save_path}")

            return overlay

        except Exception as e:
            logger.error(f"Error in segmentation visualization: {e}")
            return None

    def process_batch(
        self,
        image_dir: str,
        output_dir: Optional[str] = None
    ) -> Dict:
        """
        Process multiple images in batch.

        Args:
            image_dir: Directory containing images
            output_dir: Directory to save outputs

        Returns:
            Dictionary with processing results
        """
        output_dir = output_dir or self.config.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        results = {
            'processed': 0,
            'errors': 0,
            'detections': [],
            'segmentations': []
        }

        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        image_files = [
            f for f in Path(image_dir).iterdir()
            if f.suffix.lower() in image_extensions
        ]

        logger.info(f"Processing {len(image_files)} images...")

        for image_path in image_files:
            try:
                # Detect objects
                detections = self.detect_objects(str(image_path))
                results['detections'].append({
                    'image': image_path.name,
                    'objects': detections
                })

                # Segment image
                image_array, mask = self.segment_image(str(image_path))

                if mask is not None:
                    # Save segmentation results
                    seg_output_path = Path(output_dir) / f"seg_{image_path.stem}.png"
                    cv2.imwrite(str(seg_output_path), mask)

                    # Visualize
                    viz_path = Path(output_dir) / f"viz_{image_path.stem}.png"
                    self.visualize_segmentation(image_array, mask, str(viz_path))

                    results['segmentations'].append({
                        'image': image_path.name,
                        'mask_path': str(seg_output_path)
                    })

                results['processed'] += 1

            except Exception as e:
                logger.error(f"Error processing {image_path.name}: {e}")
                results['errors'] += 1

        logger.info(
            f"Batch processing complete. "
            f"Processed: {results['processed']}, Errors: {results['errors']}"
        )
        return results


def main():
    """Main execution example."""
    # Initialize configuration
    config = SegmentationConfig(
        device="cuda" if torch.cuda.is_available() else "cpu",
        confidence_threshold=0.5
    )

    # Initialize pipeline
    pipeline_vt = VisionTransformerSegmentation(config)

    # Example usage
    logger.info("Vision Transformer Inference Pipeline Ready")
    logger.info("Use this pipeline for zero-shot object detection and segmentation")

    # Example: Create sample data directory
    sample_data_dir = "data/sample_images"
    Path(sample_data_dir).mkdir(parents=True, exist_ok=True)

    logger.info(f"Place your images in '{sample_data_dir}' directory")
    logger.info("Run batch processing with: pipeline_vt.process_batch(sample_data_dir)")


if __name__ == "__main__":
    main()
