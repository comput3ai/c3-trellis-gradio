import gradio as gr
import spaces
import os
import shutil
os.environ['SPCONV_ALGO'] = 'native'
from typing import *
import torch
import numpy as np
import imageio
from easydict import EasyDict as edict
from PIL import Image
from trellis.pipelines import TrellisImageTo3DPipeline
from trellis.representations import Gaussian, MeshExtractResult
from trellis.utils import render_utils, postprocessing_utils


MAX_SEED = np.iinfo(np.int32).max
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmp')
os.makedirs(TMP_DIR, exist_ok=True)


def start_session(req: gr.Request):
    user_dir = os.path.join(TMP_DIR, str(req.session_hash))
    os.makedirs(user_dir, exist_ok=True)


def end_session(req: gr.Request):
    user_dir = os.path.join(TMP_DIR, str(req.session_hash))
    shutil.rmtree(user_dir)


def preprocess_image(image: Image.Image) -> Image.Image:
    processed_image = pipeline.preprocess_image(image)
    return processed_image


def preprocess_images(images: List[Tuple[Image.Image, str]]) -> List[Image.Image]:
    images = [image[0] for image in images]
    processed_images = [pipeline.preprocess_image(image) for image in images]
    return processed_images


def pack_state(gs: Gaussian, mesh: MeshExtractResult) -> dict:
    return {
        'gaussian': {
            **gs.init_params,
            '_xyz': gs._xyz.cpu().numpy(),
            '_features_dc': gs._features_dc.cpu().numpy(),
            '_scaling': gs._scaling.cpu().numpy(),
            '_rotation': gs._rotation.cpu().numpy(),
            '_opacity': gs._opacity.cpu().numpy(),
        },
        'mesh': {
            'vertices': mesh.vertices.cpu().numpy(),
            'faces': mesh.faces.cpu().numpy(),
        },
    }


def unpack_state(state: dict) -> Tuple[Gaussian, edict, str]:
    gs = Gaussian(
        aabb=state['gaussian']['aabb'],
        sh_degree=state['gaussian']['sh_degree'],
        mininum_kernel_size=state['gaussian']['mininum_kernel_size'],
        scaling_bias=state['gaussian']['scaling_bias'],
        opacity_bias=state['gaussian']['opacity_bias'],
        scaling_activation=state['gaussian']['scaling_activation'],
    )
    gs._xyz = torch.tensor(state['gaussian']['_xyz'], device='cuda')
    gs._features_dc = torch.tensor(state['gaussian']['_features_dc'], device='cuda')
    gs._scaling = torch.tensor(state['gaussian']['_scaling'], device='cuda')
    gs._rotation = torch.tensor(state['gaussian']['_rotation'], device='cuda')
    gs._opacity = torch.tensor(state['gaussian']['_opacity'], device='cuda')

    mesh = edict(
        vertices=torch.tensor(state['mesh']['vertices'], device='cuda'),
        faces=torch.tensor(state['mesh']['faces'], device='cuda'),
    )

    return gs, mesh


def get_seed(randomize_seed: bool, seed: int) -> int:
    return np.random.randint(0, MAX_SEED) if randomize_seed else seed


@spaces.GPU
def image_to_3d(
    image: Image.Image,
    multiimages: List[Tuple[Image.Image, str]],
    is_multiimage: bool,
    seed: int,
    ss_guidance_strength: float,
    ss_sampling_steps: int,
    slat_guidance_strength: float,
    slat_sampling_steps: int,
    multiimage_algo: Literal["multidiffusion", "stochastic"],
    req: gr.Request,
) -> Tuple[dict, str]:
    user_dir = os.path.join(TMP_DIR, str(req.session_hash))
    if not is_multiimage:
        outputs = pipeline.run(
            image,
            seed=seed,
            formats=["gaussian", "mesh"],
            preprocess_image=False,
            sparse_structure_sampler_params={
                "steps": ss_sampling_steps,
                "cfg_strength": ss_guidance_strength,
            },
            slat_sampler_params={
                "steps": slat_sampling_steps,
                "cfg_strength": slat_guidance_strength,
            },
        )
    else:
        outputs = pipeline.run_multi_image(
            [image[0] for image in multiimages],
            seed=seed,
            formats=["gaussian", "mesh"],
            preprocess_image=False,
            sparse_structure_sampler_params={
                "steps": ss_sampling_steps,
                "cfg_strength": ss_guidance_strength,
            },
            slat_sampler_params={
                "steps": slat_sampling_steps,
                "cfg_strength": slat_guidance_strength,
            },
            mode=multiimage_algo,
        )
    video = render_utils.render_video(outputs['gaussian'][0], num_frames=120)['color']
    video_geo = render_utils.render_video(outputs['mesh'][0], num_frames=120)['normal']

    # Solo usamos el video de color, eliminamos la concatenación
    video = video
    video_path = os.path.join(user_dir, 'sample.mp4')
    imageio.mimsave(video_path, video, fps=15)
    state = pack_state(outputs['gaussian'][0], outputs['mesh'][0])
    torch.cuda.empty_cache()
    return state, video_path


@spaces.GPU(duration=90)
def extract_glb(
    state: dict,
    mesh_simplify: float,
    texture_size: int,
    req: gr.Request,
) -> Tuple[str, str]:
    user_dir = os.path.join(TMP_DIR, str(req.session_hash))
    gs, mesh = unpack_state(state)
    glb = postprocessing_utils.to_glb(gs, mesh, simplify=mesh_simplify, texture_size=texture_size, verbose=False)
    glb_path = os.path.join(user_dir, 'sample.glb')
    glb.export(glb_path)
    torch.cuda.empty_cache()
    return glb_path, glb_path


@spaces.GPU
def extract_gaussian(state: dict, req: gr.Request) -> Tuple[str, str]:
    user_dir = os.path.join(TMP_DIR, str(req.session_hash))
    gs, _ = unpack_state(state)
    gaussian_path = os.path.join(user_dir, 'sample.ply')
    gs.save_ply(gaussian_path)
    torch.cuda.empty_cache()
    return gaussian_path, gaussian_path


def prepare_multi_example() -> List[Image.Image]:
    multi_case = list(set([i.split('_')[0] for i in os.listdir("assets/example_multi_image")]))
    images = []
    for case in multi_case:
        _images = []
        for i in range(1, 4):
            img = Image.open(f'assets/example_multi_image/{case}_{i}.png')
            W, H = img.size
            img = img.resize((int(W / H * 512), 512))
            _images.append(np.array(img))
        images.append(Image.fromarray(np.concatenate(_images, axis=1)))
    return images


def split_image(image: Image.Image) -> List[Image.Image]:
    image = np.array(image)
    alpha = image[..., 3]
    alpha = np.any(alpha>0, axis=0)
    start_pos = np.where(~alpha[:-1] & alpha[1:])[0].tolist()
    end_pos = np.where(alpha[:-1] & ~alpha[1:])[0].tolist()
    images = []
    for s, e in zip(start_pos, end_pos):
        images.append(Image.fromarray(image[:, s:e+1]))
    return [preprocess_image(image) for image in images]


with gr.Blocks(delete_cache=(600, 600)) as demo:
    gr.Markdown("""
    # TRELLIS - Image to 3D Asset
    ## 3D Asset Generation with [TRELLIS](https://trellis3d.github.io/)

    * **Single Image**: Upload one image to generate a 3D asset
    * **Multiple Images**: Upload multiple views of the same object for better results
    * Click "Generate" to create your 3D model
    """)

    with gr.Row(equal_height=False):
        # Left column (Controls)
        with gr.Column(scale=2, min_width=400):
            with gr.Tabs() as input_tabs:
                with gr.Tab(label="Single Image", id=0) as single_image_input_tab:
                    image_prompt = gr.Image(
                        label="Image Prompt",
                        format="png",
                        image_mode="RGBA",
                        type="pil",
                        height=300,
                        show_label=False
                    )
                with gr.Tab(label="Multiple Images", id=1) as multiimage_input_tab:
                    multiimage_prompt = gr.Gallery(
                        label="Image Prompt",
                        format="png",
                        type="pil",
                        height=300,
                        columns=3,
                        show_label=False
                    )
                    gr.Markdown("""
                        Input different views of the object in separate images.

                        *NOTE: This is experimental - works best with consistent views of the same object.*
                    """)

            with gr.Accordion("Generation Settings", open=False):
                with gr.Column(variant="panel"):
                    seed = gr.Slider(0, MAX_SEED, label="Seed", value=0, step=1)
                    randomize_seed = gr.Checkbox(label="Randomize Seed", value=True)

                    with gr.Group():
                        gr.Markdown("#### Stage 1: Structure")
                        ss_guidance_strength = gr.Slider(0.0, 10.0, label="Guidance", value=7.5, step=0.1)
                        ss_sampling_steps = gr.Slider(1, 50, label="Steps", value=12, step=1)

                    with gr.Group():
                        gr.Markdown("#### Stage 2: Detail")
                        slat_guidance_strength = gr.Slider(0.0, 10.0, label="Guidance", value=3.0, step=0.1)
                        slat_sampling_steps = gr.Slider(1, 50, label="Steps", value=12, step=1)

                    multiimage_algo = gr.Radio(["stochastic", "multidiffusion"], label="Multi-image Algorithm", value="stochastic")

            generate_btn = gr.Button("Generate 3D Asset", variant="primary", size="lg")

            with gr.Accordion("GLB Export Settings", open=False):
                with gr.Column(variant="panel"):
                    mesh_simplify = gr.Slider(0.5, 0.98, label="Simplify Mesh", value=0.95, step=0.01)
                    texture_size = gr.Slider(512, 2048, label="Texture Size", value=1024, step=512)

            with gr.Row():
                extract_glb_btn = gr.Button("Export GLB", interactive=False, size="lg")
                extract_gs_btn = gr.Button("Export Gaussian", interactive=False, size="lg")

        # Right column (Outputs)
        with gr.Column(scale=3, min_width=600):
            with gr.Group():
                video_output = gr.Video(
                    label="3D Preview",
                    autoplay=True,
                    loop=True,
                    height=300,
                    show_label=False
                )
                model_output = gr.Model3D(
                    label="3D Model Viewer",
                    height=400
                )

            with gr.Row():
                download_glb = gr.DownloadButton(
                    label="Download GLB File",
                    interactive=False,
                    variant="secondary",
                    size="lg"
                )
                download_gs = gr.DownloadButton(
                    label="Download Gaussian",
                    interactive=False,
                    variant="secondary",
                    size="lg"
                )

    is_multiimage = gr.State(False)
    output_buf = gr.State()

    # Example images at the bottom of the page
    with gr.Row() as single_image_example:
        examples = gr.Examples(
            examples=[
                f'assets/example_image/{image}'
                for image in sorted(os.listdir("assets/example_image"))
            ],
            inputs=[image_prompt],
            fn=preprocess_image,
            outputs=[image_prompt],
            run_on_click=True,
            examples_per_page=64,
        )
    with gr.Row(visible=False) as multiimage_example:
        examples_multi = gr.Examples(
            examples=prepare_multi_example(),
            inputs=[image_prompt],
            fn=split_image,
            outputs=[multiimage_prompt],
            run_on_click=True,
            examples_per_page=8,
        )

    # Handlers
    demo.load(start_session)
    demo.unload(end_session)

    single_image_input_tab.select(
        lambda: tuple([False, gr.Row.update(visible=True), gr.Row.update(visible=False)]),
        outputs=[is_multiimage, single_image_example, multiimage_example]
    )
    multiimage_input_tab.select(
        lambda: tuple([True, gr.Row.update(visible=False), gr.Row.update(visible=True)]),
        outputs=[is_multiimage, single_image_example, multiimage_example]
    )

    image_prompt.upload(
        preprocess_image,
        inputs=[image_prompt],
        outputs=[image_prompt],
    )
    multiimage_prompt.upload(
        preprocess_images,
        inputs=[multiimage_prompt],
        outputs=[multiimage_prompt],
    )

    generate_btn.click(
        get_seed,
        inputs=[randomize_seed, seed],
        outputs=[seed],
    ).then(
        image_to_3d,
        inputs=[image_prompt, multiimage_prompt, is_multiimage, seed, ss_guidance_strength, ss_sampling_steps, slat_guidance_strength, slat_sampling_steps, multiimage_algo],
        outputs=[output_buf, video_output],
    ).then(
        lambda: tuple([gr.Button(interactive=True), gr.Button(interactive=True)]),
        outputs=[extract_glb_btn, extract_gs_btn],
    )

    video_output.clear(
        lambda: tuple([gr.Button(interactive=False), gr.Button(interactive=False)]),
        outputs=[extract_glb_btn, extract_gs_btn],
    )

    extract_glb_btn.click(
        extract_glb,
        inputs=[output_buf, mesh_simplify, texture_size],
        outputs=[model_output, download_glb],
    ).then(
        lambda: gr.Button(interactive=True),
        outputs=[download_glb],
    )

    extract_gs_btn.click(
        extract_gaussian,
        inputs=[output_buf],
        outputs=[model_output, download_gs],
    ).then(
        lambda: gr.Button(interactive=True),
        outputs=[download_gs],
    )

    model_output.clear(
        lambda: gr.Button(interactive=False),
        outputs=[download_glb],
    )

# Apply monkey patch to fix Gradio's URL handling behind a proxy
import gradio.route_utils
original_get_api_call_path = gradio.route_utils.get_api_call_path

def patched_get_api_call_path(request):
    try:
        return original_get_api_call_path(request)
    except ValueError:
        path = request.url.path
        if not path:
            path = "/"
        return f"{path}/api"

# Apply the patch
gradio.route_utils.get_api_call_path = patched_get_api_call_path

if __name__ == "__main__":
    model_repo = os.environ.get("TRELLIS_MODEL_REPO", "jetx/trellis-image-large")
    print(f"Loading Trellis model from: {model_repo}")
    pipeline = TrellisImageTo3DPipeline.from_pretrained(model_repo)
    pipeline.cuda()
    try:
        pipeline.preprocess_image(Image.fromarray(np.zeros((512, 512, 3), dtype=np.uint8)))    # Preload rembg
    except:
        pass
    demo.launch(server_name="0.0.0.0", server_port=7860)
