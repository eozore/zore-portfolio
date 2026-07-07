# -*- coding: utf-8 -*-
"""
video_editor.py — Python engine to render HTML/graphics overlay PNGs and merge them
onto the HeyGen avatar talking video using FFmpeg colorkey chromakey blending.
"""

import os
import re
import sys
import json
import time
import subprocess
import logging
from PIL import Image, ImageDraw, ImageFont

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("video_editor")

def get_font(font_name="Arial", size=24):
    """
    Safely locates a TrueType font on macOS or falls back to system defaults.
    """
    paths = [
        f"/System/Library/Fonts/Supplemental/{font_name}.ttf",
        f"/System/Library/Fonts/{font_name}.ttf",
        f"/System/Library/Fonts/{font_name}.ttc",
        f"/Library/Fonts/{font_name}.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf"  # Fallback
    ]
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def parse_markdown_to_scenes(markdown_text: str):
    """
    Parses YouTube Script markdown text into list of scenes.
    Each scene is a dict with keys:
    - section: 'HOOK', 'TEORIA', etc.
    - visualCue: string inside blockquotes like "> [CENA: ...]"
    - spokenText: plain text paragraph following the cue.
    """
    scenes = []
    if not markdown_text:
        return scenes
        
    lines = markdown_text.split("\n")
    current_section = "HOOK"
    
    current_cue = ""
    current_spoken = []
    
    def flush_scene():
        nonlocal current_cue, current_spoken
        spoken = " ".join(current_spoken).strip()
        if current_cue or spoken:
            scenes.append({
                "section": current_section,
                "visualCue": current_cue,
                "spokenText": spoken
            })
            current_cue = ""
            current_spoken = []

    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
            
        # Section Header
        if line_strip.startswith("##"):
            flush_scene()
            current_section = line_strip.replace("##", "").strip()
            continue
            
        # Visual Cue blockquote, e.g. > [CENA: ...]
        if line_strip.startswith(">"):
            flush_scene()
            cue_content = line_strip.replace(">", "").strip()
            if cue_content.startswith("[") and cue_content.endswith("]"):
                cue_content = cue_content[1:-1].strip()
            current_cue = cue_content
            continue
            
        # Spoken text lines
        current_spoken.append(line_strip)
        
    flush_scene()
    return scenes

def generate_scene_slide(scene, index, project_dir, format="vertical"):
    """
    Renders visual cues (charts, codes, bullets) into a PNG frame over a green screen.
    """
    width, height = (1080, 1920) if format == "vertical" else (1920, 1080)
    
    # 1. Create a bright green-screen image (0, 255, 0)
    img = Image.new("RGB", (width, height), (0, 255, 0))
    draw = ImageDraw.Draw(img)
    
    cue = scene.get("visualCue", "").strip()
    
    # If no visual cue exists, return an empty green frame
    if not cue:
        out_path = os.path.join(project_dir, f"scene_{index}.png")
        img.save(out_path)
        return out_path
        
    # 2. Design Glassmorphic Card (Dark card over green screen)
    # Positions: centered horizontally, in the lower third for vertical videos to clear the speaker's face.
    card_margin = 60
    card_w = width - (card_margin * 2)
    card_h = 600
    card_x = card_margin
    card_y = height - card_h - 180
    
    card_bg = (24, 24, 37)  # Dark background
    
    draw.rounded_rectangle(
        [(card_x, card_y), (card_x + card_w, card_y + card_h)],
        radius=24,
        fill=card_bg,
        outline=(124, 58, 237),  # Glowing purple border
        width=4
    )
    
    # Check if scene is a scientific plot
    is_plot = "gráfico" in cue.lower() or "plot" in cue.lower() or "chart" in cue.lower()
    
    plot_file = None
    if is_plot:
        plots_dir = os.path.join(project_dir, "plots")
        if os.path.exists(plots_dir):
            plot_files = sorted([f for f in os.listdir(plots_dir) if f.endswith(".png")])
            if plot_files:
                plot_file = os.path.join(plots_dir, plot_files[min(index, len(plot_files) - 1)])
                
    if plot_file and os.path.exists(plot_file):
        try:
            plot_img = Image.open(plot_file)
            img_margin = 40
            target_w = card_w - (img_margin * 2)
            target_h = card_h - (img_margin * 2) - 60
            
            plot_img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)
            plot_w, plot_h = plot_img.size
            
            paste_x = card_x + (card_w - plot_w) // 2
            paste_y = card_y + (card_h - plot_h) // 2 + 20
            
            font_title = get_font("Arial", size=30)
            draw.text((card_x + 40, card_y + 30), "Comportamento do Modelo", fill=(255, 255, 255), font=font_title)
            img.paste(plot_img, (paste_x, paste_y))
            
            out_path = os.path.join(project_dir, f"scene_{index}.png")
            img.save(out_path)
            return out_path
        except Exception as e:
            logger.warning(f"Failed to paste plot image in slide: {e}")
            
    # Check if scene is a code listing
    is_code = "code" in cue.lower() or "código" in cue.lower()
    if is_code:
        # Draw macOS styled title bar
        dot_y = card_y + 35
        draw.ellipse([(card_x + 35, dot_y - 8), (card_x + 51, dot_y + 8)], fill=(255, 95, 87))  # Red
        draw.ellipse([(card_x + 60, dot_y - 8), (card_x + 76, dot_y + 8)], fill=(255, 189, 46)) # Yellow
        draw.ellipse([(card_x + 85, dot_y - 8), (card_x + 101, dot_y + 8)], fill=(39, 201, 63))  # Green
        
        font_title = get_font("Arial", size=26)
        font_code = get_font("Courier New", size=22)
        
        draw.text((card_x + 130, card_y + 20), "main.py", fill=(150, 150, 160), font=font_title)
        
        code_lines = [
            "import torch",
            "import torch.nn as nn",
            "",
            "class ModelOptimizer(nn.Module):",
            "    def __init__(self):",
            "        super().__init__()",
            "        self.lr = 1e-4 # Otimização"
        ]
        
        line_x = card_x + 40
        line_y = card_y + 90
        for line in code_lines:
            color = (255, 255, 255)
            if line.startswith("import") or line.startswith("class") or "def" in line:
                color = (244, 63, 94)  # Pink/rose keywords
            elif line.strip().startswith("#"):
                color = (110, 231, 183) # Light green comments
                
            draw.text((line_x, line_y), line, fill=color, font=font_code)
            line_y += 34
            
        out_path = os.path.join(project_dir, f"scene_{index}.png")
        img.save(out_path)
        return out_path
        
    # Default visual text card
    font_title = get_font("Arial", size=32)
    font_text = get_font("Arial", size=24)
    
    draw.text((card_x + 40, card_y + 40), f"Visualização - CENA {index + 1}", fill=(139, 92, 246), font=font_title)
    
    words = cue.split()
    wrapped_lines = []
    curr = []
    for w in words:
        curr.append(w)
        if len(" ".join(curr)) > 38:
            curr.pop()
            wrapped_lines.append(" ".join(curr))
            curr = [w]
    if curr:
        wrapped_lines.append(" ".join(curr))
        
    line_y = card_y + 110
    for line in wrapped_lines[:6]:
        draw.text((card_x + 40, line_y), f"• {line}", fill=(229, 231, 235), font=font_text)
        line_y += 45
        
    out_path = os.path.join(project_dir, f"scene_{index}.png")
    img.save(out_path)
    return out_path

def get_video_duration(video_path: str) -> float:
    """
    Invokes ffprobe to read the exact duration of a video.
    """
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        logger.warning(f"ffprobe failed to parse duration of {video_path}: {e}")
        return 60.0

def build_merged_video(avatar_path: str, scenes: list, project_dir: str, format="vertical") -> str:
    """
    Compiles overlay slides PNGs and blends them on top of the avatar video.
    """
    # 1. Inspect avatar duration
    duration = get_video_duration(avatar_path)
    logger.info(f"Loaded avatar video. Total duration: {duration}s")
    
    # 2. Estimate scene timings based on word counts proportions
    word_counts = [len(s.get("spokenText", "").split()) for s in scenes]
    total_words = sum(word_counts) or 1
    
    timings = []
    curr = 0.0
    for i, count in enumerate(word_counts):
        dur = (count / total_words) * duration
        dur = max(2.0, dur) # Minimum 2 seconds
        timings.append({
            "start": curr,
            "end": curr + dur,
            "duration": dur
        })
        curr += dur
        
    # Scale timings to fit actual video duration perfectly
    if curr > 0:
        factor = duration / curr
        for timing in timings:
            timing["start"] *= factor
            timing["end"] *= factor
            timing["duration"] = timing["end"] - timing["start"]

    # 3. Generate PNG slides for each scene
    slide_paths = []
    for idx, scene in enumerate(scenes):
        slide_path = generate_scene_slide(scene, idx, project_dir, format=format)
        slide_paths.append(slide_path)
        logger.info(f"Generated slide frame {idx}: {slide_path} (Duration: {timings[idx]['duration']:.2f}s)")
        
    # 4. Generate input.txt for FFmpeg concat demuxer
    concat_file = os.path.join(project_dir, "input.txt")
    with open(concat_file, "w", encoding="utf-8") as f:
        for idx, slide in enumerate(slide_paths):
            f.write(f"file '{slide}'\n")
            f.write(f"duration {timings[idx]['duration']:.4f}\n")
        # Specifying last file twice is required by FFmpeg concat demuxer quirk
        if slide_paths:
            f.write(f"file '{slide_paths[-1]}'\n")
            
    # 5. Compile overlay slides into a green-screen video (motion.mp4)
    motion_path = os.path.join(project_dir, "motion_greenscreen.mp4")
    cmd_motion = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
        "-vsync", "vfr", "-pix_fmt", "yuv420p", "-c:v", "libx264", motion_path
    ]
    logger.info("Assembling motion graphics overlay green-screen video...")
    subprocess.run(cmd_motion, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # 6. Apply chroma-key (colorkey) filter and blend the overlay onto the avatar
    final_path = os.path.join(project_dir, "final_merged.mp4")
    cmd_merge = [
        "ffmpeg", "-y", "-i", avatar_path, "-i", motion_path,
        "-filter_complex", "[1:v]colorkey=0x00FF00:0.1:0.2[overlay];[0:v][overlay]overlay=x=0:y=0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", final_path
    ]
    logger.info("Executing chromakey colorkey fusion merging...")
    subprocess.run(cmd_merge, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    logger.info(f"Video fusion completed successfully. Merged file: {final_path}")
    return final_path
