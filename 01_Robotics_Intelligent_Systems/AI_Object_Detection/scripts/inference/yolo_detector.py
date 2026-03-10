"""
YOLOv8 Real-Time Object Detection with TensorRT Optimization
Implements low-latency inference on video streams with CUDA acceleration.
"""

import cv2
import numpy as np
from ultralytics import YOLO
from pathlib import Path
from typing import Tuple, List, Dict, Optional
import logging
import time
from collections import deque

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YOLODetector:
    """Production-grade YOLOv8 detector with TensorRT optimization."""
    
    def __init__(self, model_name: str = "yolov8n.pt", device: str = "cuda", 
                 use_tensorrt: bool = True, conf_threshold: float = 0.45):
        """
        Initialize YOLO detector.
        
        Args:
            model_name: YOLOv8 model variant (n=nano, s=small, m=medium, l=large, x=xlarge)
            device: 'cuda' for GPU or 'cpu'
            use_tensorrt: Enable TensorRT optimization for lower latency
            conf_threshold: Confidence threshold for detections
        """
        self.device = device
        self.conf_threshold = conf_threshold
        self.model_name = model_name
        
        logger.info(f"Loading {model_name} on device: {device}")
        self.model = YOLO(model_name)
        
        # Export to TensorRT format if enabled and device is cuda
        if use_tensorrt and device == "cuda":
            try:
                logger.info("Exporting model to TensorRT format...")
                tensorrt_model = self.model.export(format="engine", device=device)
                self.model = YOLO(tensorrt_model)
                logger.info("TensorRT optimization enabled")
            except Exception as e:
                logger.warning(f"TensorRT export failed, using standard model: {e}")
        
        # Performance tracking
        self.inference_times = deque(maxlen=30)
        self.fps_counter = 0
        self.prev_time = time.time()
    
    def detect(self, frame: np.ndarray, conf: Optional[float] = None, 
               iou: float = 0.45) -> Tuple[np.ndarray, List[Dict]]:
        """
        Run inference on a single frame.
        
        Args:
            frame: Input image (BGR format from OpenCV)
            conf: Confidence threshold (uses self.conf_threshold if None)
            iou: IoU threshold for NMS
            
        Returns:
            Annotated frame and list of detections
        """
        if conf is None:
            conf = self.conf_threshold
        
        start_time = time.time()
        
        # Run YOLO inference
        results = self.model(frame, conf=conf, iou=iou, device=self.device, verbose=False)
        
        inference_time = time.time() - start_time
        self.inference_times.append(inference_time)
        
        # Extract detections
        detections = []
        annotated_frame = frame.copy()
        
        if results and len(results) > 0:
            result = results[0]
            
            if result.boxes is not None:
                boxes = result.boxes.cpu().numpy()
                
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].astype(int)
                    conf_score = float(box.conf[0])
                    class_id = int(box.cls[0])
                    class_name = result.names[class_id]
                    
                    detection = {
                        'class_id': class_id,
                        'class_name': class_name,
                        'confidence': conf_score,
                        'bbox': (x1, y1, x2, y2),
                        'center': ((x1 + x2) // 2, (y1 + y2) // 2),
                        'area': (x2 - x1) * (y2 - y1)
                    }
                    detections.append(detection)
                    
                    # Draw bounding box
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    
                    # Draw label
                    label = f"{class_name} {conf_score:.2f}"
                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                    cv2.rectangle(annotated_frame, (x1, y1 - label_size[1] - 5),
                                 (x1 + label_size[0], y1), (0, 255, 0), -1)
                    cv2.putText(annotated_frame, label, (x1, y1 - 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        
        return annotated_frame, detections
    
    def process_video_stream(self, source: str, output_path: Optional[str] = None,
                            max_frames: Optional[int] = None, display: bool = True) -> None:
        """
        Process video stream with real-time detection.
        
        Args:
            source: Video file path or camera index (0 for webcam)
            output_path: Path to save output video (optional)
            max_frames: Maximum frames to process (None for all)
            display: Display real-time results
        """
        # Open video source
        cap = cv2.VideoCapture(source if isinstance(source, int) else str(source))
        
        if not cap.isOpened():
            logger.error(f"Failed to open video source: {source}")
            return
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        logger.info(f"Video: {width}x{height} @ {fps} FPS, {total_frames} frames")
        
        # Setup output video writer if specified
        out = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            logger.info(f"Output will be saved to {output_path}")
        
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            
            if not ret:
                logger.info("Video stream ended")
                break
            
            frame_count += 1
            
            if max_frames and frame_count > max_frames:
                logger.info(f"Reached max frames limit: {max_frames}")
                break
            
            # Run detection
            annotated_frame, detections = self.detect(frame)
            
            # Add FPS to frame
            avg_inference_time = np.mean(self.inference_times) if self.inference_times else 0
            current_fps = 1.0 / avg_inference_time if avg_inference_time > 0 else 0
            
            cv2.putText(annotated_frame, f"FPS: {current_fps:.1f} | Detections: {len(detections)}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Write to output video
            if out:
                out.write(annotated_frame)
            
            # Display
            if display:
                cv2.imshow("YOLO Detection", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    logger.info("User interrupted video processing")
                    break
            
            # Log progress
            if frame_count % 30 == 0:
                logger.info(f"Processed {frame_count}/{total_frames} frames | "
                           f"Avg FPS: {current_fps:.1f} | Detections: {len(detections)}")
        
        # Cleanup
        cap.release()
        if out:
            out.release()
        if display:
            cv2.destroyAllWindows()
        
        logger.info(f"Completed processing {frame_count} frames")
    
    def process_image(self, image_path: str, output_path: Optional[str] = None) -> Dict:
        """
        Process a single image.
        
        Args:
            image_path: Path to input image
            output_path: Path to save annotated image (optional)
            
        Returns:
            Dictionary with detections and metadata
        """
        image = cv2.imread(image_path)
        
        if image is None:
            logger.error(f"Failed to load image: {image_path}")
            return {}
        
        logger.info(f"Processing image: {image_path}")
        
        annotated_frame, detections = self.detect(image)
        
        result = {
            'image_path': image_path,
            'num_detections': len(detections),
            'detections': detections,
            'image_shape': image.shape
        }
        
        if output_path:
            cv2.imwrite(output_path, annotated_frame)
            logger.info(f"Saved annotated image to {output_path}")
        
        return result
    
    def get_performance_stats(self) -> Dict:
        """
        Get performance statistics.
        
        Returns:
            Dictionary with inference metrics
        """
        if not self.inference_times:
            return {}
        
        times = list(self.inference_times)
        
        return {
            'avg_inference_time_ms': np.mean(times) * 1000,
            'min_inference_time_ms': np.min(times) * 1000,
            'max_inference_time_ms': np.max(times) * 1000,
            'std_inference_time_ms': np.std(times) * 1000,
            'avg_fps': 1.0 / np.mean(times) if np.mean(times) > 0 else 0,
            'samples_collected': len(times)
        }


if __name__ == "__main__":
    # Example usage
    detector = YOLODetector(model_name="yolov8n.pt", device="cuda", use_tensorrt=True)
    
    # Process webcam stream
    logger.info("Starting real-time detection on webcam (press 'q' to quit)...")
    detector.process_video_stream(source=0, display=True)
    
    # Print performance stats
    stats = detector.get_performance_stats()
    logger.info(f"Performance Stats: {stats}")
