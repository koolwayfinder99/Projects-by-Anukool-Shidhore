"""
Image Preprocessing Pipeline for AI Object Detection
Implements noise reduction, normalization, and histogram equalization
for robust detection in varying lighting conditions.
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ImagePreprocessor:
    """Production-grade image preprocessing for object detection models."""
    
    def __init__(self, target_size: Tuple[int, int] = (640, 640)):
        """
        Initialize the image preprocessor.
        
        Args:
            target_size: Target resolution (height, width)
        """
        self.target_size = target_size
        self.kernel_size = (5, 5)  # For Gaussian blur
        
    def apply_gaussian_blur(self, image: np.ndarray, kernel_size: int = 5) -> np.ndarray:
        """
        Apply Gaussian blur for noise reduction.
        
        Args:
            image: Input image
            kernel_size: Size of the Gaussian kernel (odd number)
            
        Returns:
            Blurred image
        """
        if kernel_size % 2 == 0:
            kernel_size += 1
        return cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
    
    def apply_bilateral_filter(self, image: np.ndarray, d: int = 9, 
                               sigma_color: float = 75, sigma_space: float = 75) -> np.ndarray:
        """
        Apply bilateral filtering for edge-preserving noise reduction.
        Superior to Gaussian blur for maintaining object boundaries.
        
        Args:
            image: Input image
            d: Diameter of pixel neighborhood
            sigma_color: Filter sigma in the color space
            sigma_space: Filter sigma in the coordinate space
            
        Returns:
            Filtered image
        """
        return cv2.bilateralFilter(image, d, sigma_color, sigma_space)
    
    def normalize_image(self, image: np.ndarray, method: str = 'minmax') -> np.ndarray:
        """
        Normalize image pixel values.
        
        Args:
            image: Input image
            method: 'minmax' (0-1 range) or 'zscore' (standardization)
            
        Returns:
            Normalized image (float32)
        """
        image = image.astype(np.float32)
        
        if method == 'minmax':
            # Min-max normalization: (x - min) / (max - min)
            min_val = image.min()
            max_val = image.max()
            if max_val > min_val:
                image = (image - min_val) / (max_val - min_val)
            else:
                image = np.zeros_like(image)
                
        elif method == 'zscore':
            # Z-score normalization: (x - mean) / std
            mean = image.mean()
            std = image.std()
            if std > 0:
                image = (image - mean) / std
                
        return image
    
    def histogram_equalization(self, image: np.ndarray, method: str = 'clahe') -> np.ndarray:
        """
        Apply histogram equalization for improved contrast.
        CLAHE is superior for preserving local details.
        
        Args:
            image: Input image
            method: 'standard' (global) or 'clahe' (Contrast Limited Adaptive)
            
        Returns:
            Equalized image
        """
        if len(image.shape) == 3 and image.shape[2] == 3:
            # Convert BGR to LAB color space for better results
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l_channel = lab[:, :, 0]
            
            if method == 'clahe':
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                l_channel = clahe.apply(l_channel)
            else:
                l_channel = cv2.equalizeHist(l_channel)
            
            lab[:, :, 0] = l_channel
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            # Grayscale image
            if method == 'clahe':
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                return clahe.apply(image)
            else:
                return cv2.equalizeHist(image)
    
    def resize_image(self, image: np.ndarray, target_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
        """
        Resize image while maintaining aspect ratio (letterboxing).
        
        Args:
            image: Input image
            target_size: Target (width, height). Uses self.target_size if None.
            
        Returns:
            Resized image
        """
        if target_size is None:
            target_size = self.target_size
        
        h, w = image.shape[:2]
        target_h, target_w = target_size
        
        # Calculate scale to fit image within target
        scale = min(target_w / w, target_h / h)
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        # Resize
        resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Letterbox with gray padding
        canvas = np.full((target_h, target_w, 3), 128, dtype=np.uint8)
        start_x = (target_w - new_w) // 2
        start_y = (target_h - new_h) // 2
        canvas[start_y:start_y + new_h, start_x:start_x + new_w] = resized
        
        return canvas
    
    def process_pipeline(self, image: np.ndarray, 
                        apply_blur: bool = True,
                        blur_type: str = 'bilateral',
                        apply_equalization: bool = True,
                        eq_method: str = 'clahe',
                        normalize: bool = True,
                        norm_method: str = 'minmax',
                        resize: bool = True) -> np.ndarray:
        """
        Complete preprocessing pipeline with multiple stages.
        
        Args:
            image: Input image
            apply_blur: Apply noise reduction
            blur_type: 'gaussian' or 'bilateral'
            apply_equalization: Apply histogram equalization
            eq_method: 'standard' or 'clahe'
            normalize: Apply normalization
            norm_method: 'minmax' or 'zscore'
            resize: Resize to target dimensions
            
        Returns:
            Preprocessed image
        """
        logger.info(f"Input image shape: {image.shape}")
        
        # Stage 1: Noise Reduction
        if apply_blur:
            if blur_type == 'bilateral':
                image = self.apply_bilateral_filter(image)
            else:
                image = self.apply_gaussian_blur(image)
            logger.info("Applied noise reduction (blur)")
        
        # Stage 2: Histogram Equalization for contrast enhancement
        if apply_equalization:
            image = self.histogram_equalization(image, method=eq_method)
            logger.info(f"Applied histogram equalization ({eq_method})")
        
        # Stage 3: Normalization
        if normalize:
            image = self.normalize_image(image, method=norm_method)
            logger.info(f"Applied normalization ({norm_method})")
        
        # Stage 4: Resizing
        if resize:
            image = self.resize_image(image)
            logger.info(f"Resized to {self.target_size}")
        
        logger.info(f"Output image shape: {image.shape}, dtype: {image.dtype}")
        return image
    
    def process_batch(self, image_paths: list, output_dir: Optional[str] = None) -> list:
        """
        Process multiple images efficiently.
        
        Args:
            image_paths: List of paths to images
            output_dir: Directory to save processed images (optional)
            
        Returns:
            List of processed images
        """
        processed_images = []
        
        for img_path in image_paths:
            try:
                image = cv2.imread(str(img_path))
                if image is None:
                    logger.warning(f"Failed to load {img_path}")
                    continue
                
                processed = self.process_pipeline(image)
                processed_images.append(processed)
                
                if output_dir:
                    Path(output_dir).mkdir(parents=True, exist_ok=True)
                    output_path = Path(output_dir) / Path(img_path).name
                    cv2.imwrite(str(output_path), (processed * 255).astype(np.uint8))
                    logger.info(f"Saved to {output_path}")
                    
            except Exception as e:
                logger.error(f"Error processing {img_path}: {e}")
        
        return processed_images


if __name__ == "__main__":
    # Example usage
    preprocessor = ImagePreprocessor(target_size=(640, 640))
    
    # Process a sample image
    sample_image_path = "data/samples/sample.jpg"
    
    if Path(sample_image_path).exists():
        image = cv2.imread(sample_image_path)
        processed = preprocessor.process_pipeline(image)
        
        # Display results
        cv2.namedWindow("Original vs Processed", cv2.WINDOW_NORMAL)
        comparison = np.hstack([
            cv2.cvtColor((image * 255).astype(np.uint8) if image.dtype == np.float32 else image, cv2.COLOR_BGR2RGB),
            cv2.cvtColor((processed * 255).astype(np.uint8) if processed.dtype == np.float32 else processed, cv2.COLOR_BGR2RGB)
        ])
        cv2.imshow("Original vs Processed", comparison)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        logger.warning(f"Sample image not found at {sample_image_path}")
