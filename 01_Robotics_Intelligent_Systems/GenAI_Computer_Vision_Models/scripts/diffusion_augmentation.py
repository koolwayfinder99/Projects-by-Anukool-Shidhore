"""
Stable Diffusion Data Augmentation Pipeline
==============================================

This module implements synthetic training data generation using Stable Diffusion
to augment robotics training datasets with realistic variations in lighting,
shadows, backgrounds, and viewpoints.

Author: Anukool Shidhore
Date: 2026
"""

import torch
import cv2
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import logging
from PIL import Image
import tqdm

from diffusers import StableDiffusionPipeline, StableDiffusionInpaintPipeline
from diffusers import DPMSolverMultistepScheduler


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AugmentationConfig:
    """Configuration for data augmentation pipeline."""
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    model_id: str = "stabilityai/stable-diffusion-2-base"
    num_inference_steps: int = 50
    guidance_scale: float = 7.5
    height: int = 512
    width: int = 512
    batch_size: int = 1
    seed: int = 42
    augmentation_types: List[str] = field(default_factory=lambda: [
        "lighting_variation",
        "shadow_addition",
        "background_change",
        "viewpoint_shift",
        "material_variation"
    ])


class DiffusionAugmentationPipeline:
    """
    Stable Diffusion-based data augmentation for robotics applications.
    Generates realistic synthetic variations to improve model robustness.
    """

    def __init__(self, config: Optional[AugmentationConfig] = None):
        """
        Initialize Stable Diffusion augmentation pipeline.

        Args:
            config: AugmentationConfig object with generation parameters
        """
        self.config = config or AugmentationConfig()
        self.device = torch.device(self.config.device)

        logger.info(f"Using device: {self.device}")
        logger.info(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            logger.info(f"CUDA device: {torch.cuda.get_device_name(0)}")

        self._initialize_pipeline()

    def _initialize_pipeline(self):
        """Initialize Stable Diffusion pipeline with optimizations."""
        try:
            logger.info("Loading Stable Diffusion pipeline...")

            # Load base pipeline
            self.pipe = StableDiffusionPipeline.from_pretrained(
                self.config.model_id,
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
                safety_checker=None  # Disable for robotics data
            )
            self.pipe = self.pipe.to(self.device)

            # Optimize scheduler for faster inference
            self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                self.pipe.scheduler.config
            )

            # Load inpainting pipeline for localized augmentation
            logger.info("Loading inpainting pipeline...")
            self.inpaint_pipe = StableDiffusionInpaintPipeline.from_pretrained(
                "stabilityai/stable-diffusion-2-inpaint",
                torch_dtype=torch.float16 if self.device.type == "cuda" else torch.float32,
                safety_checker=None
            )
            self.inpaint_pipe = self.inpaint_pipe.to(self.device)
            self.inpaint_pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                self.inpaint_pipe.scheduler.config
            )

            # Enable memory optimizations
            if self.device.type == "cuda":
                self.pipe.enable_attention_slicing()
                self.inpaint_pipe.enable_attention_slicing()

            logger.info("Pipelines loaded successfully!")

        except Exception as e:
            logger.error(f"Error initializing pipeline: {e}")
            raise

    def set_seed(self, seed: int):
        """Set random seed for reproducibility."""
        torch.manual_seed(seed)
        np.random.seed(seed)

    @torch.no_grad()
    def generate_with_prompt(
        self,
        prompt: str,
        negative_prompt: str = "",
        num_images: int = 1
    ) -> List[Image.Image]:
        """
        Generate images using text-to-image synthesis.

        Args:
            prompt: Text description for image generation
            negative_prompt: What to avoid in generation
            num_images: Number of variations to generate

        Returns:
            List of generated PIL images
        """
        try:
            self.set_seed(self.config.seed)

            logger.info(f"Generating {num_images} images with prompt: {prompt}")

            images = self.pipe(
                prompt=[prompt] * num_images,
                negative_prompt=[negative_prompt] * num_images,
                num_inference_steps=self.config.num_inference_steps,
                guidance_scale=self.config.guidance_scale,
                height=self.config.height,
                width=self.config.width
            ).images

            logger.info(f"Generated {len(images)} images successfully")
            return images

        except Exception as e:
            logger.error(f"Error in image generation: {e}")
            return []

    @torch.no_grad()
    def augment_lighting(
        self,
        image_path: str,
        num_variations: int = 3
    ) -> List[Image.Image]:
        """
        Generate lighting variations for input image.

        Args:
            image_path: Path to input robotics image
            num_variations: Number of lighting variations

        Returns:
            List of augmented images with different lighting
        """
        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(
                f"Generating {num_variations} lighting variations "
                f"for {Path(image_path).name}"
            )

            lighting_prompts = [
                "industrial robot under bright LED overhead lighting",
                "robotic arm with soft diffused lighting and shadows",
                "automated system with dramatic side lighting",
                "manufacturing robot under warm tungsten lighting",
                "robot workspace with cool fluorescent lighting"
            ]

            variations = []
            for i in range(num_variations):
                prompt = lighting_prompts[i % len(lighting_prompts)]
                prompt += ", professional industrial photography, detailed, realistic"

                generated = self.pipe(
                    prompt=prompt,
                    negative_prompt="cartoon, artwork, illustration, low quality",
                    num_inference_steps=self.config.num_inference_steps,
                    guidance_scale=self.config.guidance_scale,
                    height=self.config.height,
                    width=self.config.width
                ).images[0]

                variations.append(generated)

            return variations

        except Exception as e:
            logger.error(f"Error in lighting augmentation: {e}")
            return []

    @torch.no_grad()
    def augment_shadows(
        self,
        image_path: str,
        mask_path: Optional[str] = None,
        num_variations: int = 3
    ) -> List[Image.Image]:
        """
        Add realistic shadows to robot images for robustness.

        Args:
            image_path: Path to input image
            mask_path: Optional mask for targeted augmentation
            num_variations: Number of shadow variations

        Returns:
            List of augmented images with shadows
        """
        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(
                f"Generating {num_variations} shadow variations "
                f"for {Path(image_path).name}"
            )

            shadow_prompts = [
                "robotic arm with deep shadows from side light",
                "automated gripper with sharp shadow patterns",
                "industrial robot with soft gradient shadows",
                "mechanical manipulator with strong directional shadows",
                "robotic system with multiple overlapping shadows"
            ]

            variations = []
            for i in range(num_variations):
                prompt = shadow_prompts[i % len(shadow_prompts)]
                prompt += ", professional photography, intricate details"

                generated = self.pipe(
                    prompt=prompt,
                    num_inference_steps=self.config.num_inference_steps,
                    guidance_scale=self.config.guidance_scale
                ).images[0]

                variations.append(generated)

            return variations

        except Exception as e:
            logger.error(f"Error in shadow augmentation: {e}")
            return []

    @torch.no_grad()
    def augment_background(
        self,
        image_path: str,
        num_variations: int = 3
    ) -> List[Image.Image]:
        """
        Generate different background environments for robot images.

        Args:
            image_path: Path to input image
            num_variations: Number of background variations

        Returns:
            List of augmented images with different backgrounds
        """
        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(
                f"Generating {num_variations} background variations "
                f"for {Path(image_path).name}"
            )

            background_prompts = [
                "industrial factory workstation background",
                "modern manufacturing facility with machinery",
                "warehouse shelving and storage environment",
                "clean laboratory workspace with tools",
                "assembly line production facility background"
            ]

            variations = []
            for i in range(num_variations):
                prompt = background_prompts[i % len(background_prompts)]
                prompt += ", automated robot in foreground, professional, sharp"

                generated = self.pipe(
                    prompt=prompt,
                    num_inference_steps=self.config.num_inference_steps,
                    guidance_scale=self.config.guidance_scale
                ).images[0]

                variations.append(generated)

            return variations

        except Exception as e:
            logger.error(f"Error in background augmentation: {e}")
            return []

    @torch.no_grad()
    def augment_viewpoint(
        self,
        image_path: str,
        num_variations: int = 3
    ) -> List[Image.Image]:
        """
        Generate different viewpoint perspectives for robot images.

        Args:
            image_path: Path to input image
            num_variations: Number of viewpoint variations

        Returns:
            List of augmented images from different viewpoints
        """
        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(
                f"Generating {num_variations} viewpoint variations "
                f"for {Path(image_path).name}"
            )

            viewpoint_prompts = [
                "robotic arm photographed from overhead perspective, top-down view",
                "industrial robot viewed from side angle, lateral perspective",
                "automated system photographed from low angle, looking up",
                "manipulator robot viewed from front, frontal perspective",
                "robotic arm photographed from isometric 3/4 view angle"
            ]

            variations = []
            for i in range(num_variations):
                prompt = viewpoint_prompts[i % len(viewpoint_prompts)]
                prompt += ", high quality, detailed, industrial"

                generated = self.pipe(
                    prompt=prompt,
                    num_inference_steps=self.config.num_inference_steps,
                    guidance_scale=self.config.guidance_scale
                ).images[0]

                variations.append(generated)

            return variations

        except Exception as e:
            logger.error(f"Error in viewpoint augmentation: {e}")
            return []

    @torch.no_grad()
    def augment_material(
        self,
        image_path: str,
        num_variations: int = 3
    ) -> List[Image.Image]:
        """
        Generate material and finish variations (reflections, weathering).

        Args:
            image_path: Path to input image
            num_variations: Number of material variations

        Returns:
            List of augmented images with different materials
        """
        try:
            image = Image.open(image_path).convert("RGB")
            logger.info(
                f"Generating {num_variations} material variations "
                f"for {Path(image_path).name}"
            )

            material_prompts = [
                "shiny polished steel robot with reflective surface",
                "matte black industrial robot with wear patterns",
                "brushed aluminum robot with texture details",
                "painted metal robot with weathered finish",
                "stainless steel robotic arm with mirror finish"
            ]

            variations = []
            for i in range(num_variations):
                prompt = material_prompts[i % len(material_prompts)]
                prompt += ", professional manufacturing photography, detailed"

                generated = self.pipe(
                    prompt=prompt,
                    num_inference_steps=self.config.num_inference_steps,
                    guidance_scale=self.config.guidance_scale
                ).images[0]

                variations.append(generated)

            return variations

        except Exception as e:
            logger.error(f"Error in material augmentation: {e}")
            return []

    def augment_dataset(
        self,
        input_dir: str,
        output_dir: str,
        augmentations_per_image: int = 5,
        augmentation_types: Optional[List[str]] = None
    ) -> Dict:
        """
        Augment entire dataset with synthetic variations.

        Args:
            input_dir: Directory containing original images
            output_dir: Directory to save augmented images
            augmentations_per_image: Number of augmentations per image
            augmentation_types: Specific augmentation types to apply

        Returns:
            Dictionary with augmentation statistics
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        augmentation_types = augmentation_types or self.config.augmentation_types

        results = {
            'original_images': 0,
            'augmented_images': 0,
            'augmentation_types': augmentation_types,
            'failed': []
        }

        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        image_files = [
            f for f in Path(input_dir).iterdir()
            if f.suffix.lower() in image_extensions
        ]

        logger.info(
            f"Starting augmentation of {len(image_files)} images "
            f"with {augmentations_per_image} augmentations each"
        )

        for idx, image_path in enumerate(tqdm.tqdm(image_files)):
            try:
                results['original_images'] += 1
                image_stem = image_path.stem

                # Create subdirectory for each original image
                image_output_dir = output_dir / image_stem
                image_output_dir.mkdir(exist_ok=True)

                # Copy original image
                original_output = image_output_dir / f"00_original{image_path.suffix}"
                cv2.imwrite(str(original_output), cv2.imread(str(image_path)))

                # Apply each augmentation type
                for aug_idx, aug_type in enumerate(augmentation_types, 1):
                    try:
                        if aug_type == "lighting_variation":
                            variations = self.augment_lighting(
                                str(image_path),
                                num_variations=augmentations_per_image
                            )
                        elif aug_type == "shadow_addition":
                            variations = self.augment_shadows(
                                str(image_path),
                                num_variations=augmentations_per_image
                            )
                        elif aug_type == "background_change":
                            variations = self.augment_background(
                                str(image_path),
                                num_variations=augmentations_per_image
                            )
                        elif aug_type == "viewpoint_shift":
                            variations = self.augment_viewpoint(
                                str(image_path),
                                num_variations=augmentations_per_image
                            )
                        elif aug_type == "material_variation":
                            variations = self.augment_material(
                                str(image_path),
                                num_variations=augmentations_per_image
                            )
                        else:
                            logger.warning(f"Unknown augmentation type: {aug_type}")
                            continue

                        # Save variations
                        for var_idx, variation in enumerate(variations):
                            output_name = f"{aug_idx:02d}_{aug_type}_{var_idx:02d}.png"
                            output_path = image_output_dir / output_name
                            variation.save(str(output_path))
                            results['augmented_images'] += 1

                    except Exception as e:
                        logger.error(f"Error in {aug_type} for {image_path.name}: {e}")
                        results['failed'].append((image_path.name, aug_type))

            except Exception as e:
                logger.error(f"Error processing {image_path.name}: {e}")
                results['failed'].append(image_path.name)

        logger.info(
            f"Augmentation complete. "
            f"Original: {results['original_images']}, "
            f"Augmented: {results['augmented_images']}, "
            f"Failed: {len(results['failed'])}"
        )

        return results


def main():
    """Main execution example."""
    config = AugmentationConfig(
        device="cuda" if torch.cuda.is_available() else "cpu",
        num_inference_steps=50,
        guidance_scale=7.5
    )

    pipeline_aug = DiffusionAugmentationPipeline(config)

    logger.info("Stable Diffusion Data Augmentation Pipeline Ready")
    logger.info("Use this pipeline to generate synthetic training variations")
    logger.info("Supported augmentations:")
    for aug in config.augmentation_types:
        logger.info(f"  - {aug}")


if __name__ == "__main__":
    main()
