# 🎨 C3-TRELLIS-Gradio

A comprehensive comparison and implementation of different TRELLIS model variants for 3D asset generation from images. This project analyzes and consolidates multiple TRELLIS implementations to create an optimized Gradio interface.

## 🎯 Project Overview

This project examines four different TRELLIS implementations:
- 🔧 **FurkanGozukara-TRELLIS**: Extended implementation with API and additional features
- ⚡ **TRELLIS-Imagen3D**: Simplified, working implementation by cavargas10
- 🎯 **TRELLIS-innoai**: Multi-image support with both single and multi-image tabs
- 🌐 **microsoft-TRELLIS**: The original official implementation

The main contribution is creating a unified app.py for TRELLIS-innoai that combines the best features from all implementations while removing unnecessary dependencies.

## 🚀 Key Features

### ✨ Unified Implementation
- 🎭 **Dual-mode interface**: Single image and multi-image 3D generation in one app
- 🔧 **No LitModel3D dependency**: Uses standard Gradio components for better compatibility
- ✂️ **Split image functionality**: Automatically splits concatenated multi-view images
- ✨ **Clean UI**: Based on the working TRELLIS-Imagen3D interface design

### 🖼️ Multi-Image Support
- 📷 Upload multiple views of the same object for improved 3D reconstruction
- 🎲 Supports both stochastic and multidiffusion algorithms
- 🧪 Experimental feature that works best with consistent object views

### 📦 Export Options
- 🎮 **GLB files**: Industry-standard 3D format with texture
- ✨ **Gaussian splats**: PLY format for 3D Gaussian representation
- 🏛️ Adjustable mesh simplification and texture resolution

## 📋 Implementation Details

### 🔄 Key Changes Made
1. 🚫 **Removed gradio_litmodel3d dependency**: Replaced with standard `gr.Model3D`
2. ✅ **Preserved split_image functionality**: Essential for processing multi-view images
3. 🔗 **Unified configuration**: Server runs on `0.0.0.0:7860` like Imagen3D
4. 🧤 **Simplified codebase**: Removed unnecessary docstrings while maintaining functionality

### ⚙️ Technical Architecture
```python
# Core pipeline configuration
pipeline = TrellisImageTo3DPipeline.from_pretrained("jetx/trellis-image-large")
pipeline.cuda()

# Two-stage generation process
# Stage 1: Sparse Structure Generation (guidance: 7.5, steps: 12)
# Stage 2: Detail Enhancement (guidance: 3.0, steps: 12)
```

## 🔧 Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/c3-trellis-gradio.git
cd c3-trellis-gradio
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:7860`

## 🏆 Honorable Mentions

This project builds upon and references several TRELLIS implementations:

### 🏛️ Original Implementation
- **[microsoft/TRELLIS](https://github.com/microsoft/TRELLIS)**: The official TRELLIS repository with full training code and documentation
- **Paper**: [Structured 3D Latents for Scalable and Versatile 3D Generation](https://arxiv.org/abs/2412.01506)

### 🤗 Hugging Face Spaces
- **[cavargas10/TRELLIS-Imagen3D](https://huggingface.co/spaces/cavargas10/TRELLIS-Imagen3D)**: Clean, working implementation that served as the base for our unified approach
- **[innoai/TRELLIS](https://huggingface.co/spaces/innoai/TRELLIS)**: Implementation with multi-image support that inspired our dual-mode interface

### 🧠 Model Weights
- **[jetx/trellis-image-large](https://huggingface.co/jetx/trellis-image-large)**: Mirror of the TRELLIS model weights on Hugging Face

## 💡 Usage Example

```python
import os
os.environ['SPCONV_ALGO'] = 'native'

from PIL import Image
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.utils import render_utils, postprocessing_utils

# Load pipeline
pipeline = TrellisImageTo3DPipeline.from_pretrained("jetx/trellis-image-large")
pipeline.cuda()

# Single image generation
image = Image.open("path/to/image.png")
outputs = pipeline.run(image, seed=1)

# Extract outputs
glb = postprocessing_utils.to_glb(
    outputs['gaussian'][0],
    outputs['mesh'][0],
    simplify=0.95,
    texture_size=1024
)
glb.export("output.glb")
```

## 🛠️ Project Structure

```
c3-trellis-gradio/
├── TRELLIS-innoai/          # Unified implementation
│   ├── app.py               # Main Gradio interface
│   ├── requirements.txt     # Dependencies (no litmodel3d)
│   └── assets/              # Example images
├── TRELLIS-Imagen3D/        # Reference implementation
├── FurkanGozukara-TRELLIS/  # Extended features
└── microsoft-TRELLIS/       # Original implementation
```

## 📄 License

This project is licensed under the MIT License, following the original TRELLIS licensing.

## 🙏 Acknowledgments

Special thanks to:
- 💙 The Microsoft Research team for creating TRELLIS
- ⭐ cavargas10 for the clean Imagen3D implementation
- 🌟 innoai for the multi-image support implementation
- 🤗 The Hugging Face community for hosting the demos and models

## 📜 Citation

If you use this project, please cite the original TRELLIS paper:

```bibtex
@article{xiang2024structured,
    title   = {Structured 3D Latents for Scalable and Versatile 3D Generation},
    author  = {Xiang, Jianfeng and Lv, Zelong and Xu, Sicheng and Deng, Yu and Wang, Ruicheng and Zhang, Bowen and Chen, Dong and Tong, Xin and Yang, Jiaolong},
    journal = {arXiv preprint arXiv:2412.01506},
    year    = {2024}
}
```