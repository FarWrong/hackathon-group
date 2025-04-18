import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import transforms
from utils.file_writer import percentage_queue

from utils.datasets import Gaze360, MPIIGaze

from models import (
    resnet18,
    resnet34,
    resnet50,
    mobilenet_v2,
    mobileone_s0,
    mobileone_s1,
    mobileone_s2,
    mobileone_s3,
    mobileone_s4
)

looks_count = 0
no_looks_count = 0
total_faces = 0

def get_model(arch, bins, pretrained=False, inference_mode=False):
    """Return the model based on the specified architecture."""
    if arch == 'resnet18':
        model = resnet18(pretrained=pretrained, num_classes=bins)
    elif arch == 'resnet34':
        model = resnet34(pretrained=pretrained, num_classes=bins)
    elif arch == 'resnet50':
        model = resnet50(pretrained=pretrained, num_classes=bins)
    elif arch == "mobilenetv2":
        model = mobilenet_v2(pretrained=pretrained, num_classes=bins)
    elif arch == "mobileone_s0":
        model = mobileone_s0(pretrained=pretrained, num_classes=bins, inference_mode=inference_mode)
    elif arch == "mobileone_s1":
        model = mobileone_s1(pretrained=pretrained, num_classes=bins, inference_mode=inference_mode)
    elif arch == "mobileone_s2":
        model = mobileone_s2(pretrained=pretrained, num_classes=bins, inference_mode=inference_mode)
    elif arch == "mobileone_s3":
        model = mobileone_s3(pretrained=pretrained, num_classes=bins, inference_mode=inference_mode)
    elif arch == "mobileone_s4":
        model = mobileone_s4(pretrained=pretrained, num_classes=bins, inference_mode=inference_mode)
    else:
        raise ValueError(f"Please choose available model architecture, currently chosen: {arch}")
    return model


def angular_error(gaze_vector, label_vector):
    dot_product = np.dot(gaze_vector, label_vector)
    norm_product = np.linalg.norm(gaze_vector) * np.linalg.norm(label_vector)
    cosine_similarity = min(dot_product / norm_product, 0.9999999)

    return np.degrees(np.arccos(cosine_similarity))


def gaze_to_3d(gaze):
    yaw = gaze[0]   # Horizontal angle
    pitch = gaze[1]  # Vertical angle

    gaze_vector = np.zeros(3)
    gaze_vector[0] = -np.cos(pitch) * np.sin(yaw)
    gaze_vector[1] = -np.sin(pitch)
    gaze_vector[2] = -np.cos(pitch) * np.cos(yaw)

    return gaze_vector


def get_dataloader(params,  mode="train"):
    """Load dataset and return DataLoader."""

    transform = transforms.Compose([
        transforms.Resize(448),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    if params.dataset == "gaze360":
        dataset = Gaze360(params.data, transform, angle=params.angle, binwidth=params.binwidth, mode=mode)
    elif params.dataset == "mpiigaze":
        dataset = MPIIGaze(params.data, transform, angle=params.angle, binwidth=params.binwidth)
    else:
        raise ValueError("Supported dataset are `gaze360` and `mpiigaze`")

    data_loader = DataLoader(
        dataset=dataset,
        batch_size=params.batch_size,
        shuffle=True if mode == "train" else False,
        num_workers=params.num_workers,
        pin_memory=True
    )
    return data_loader


def draw_gaze(frame, bbox, pitch, yaw, attention_threshold=0.20, thickness=2):
    """Draws gaze direction on a frame given bounding box and gaze angles."""
    # unpack bbox coords
    x_min, y_min, x_max, y_max = map(int, bbox[:4])

    # calc bbox center
    x_center = (x_min + x_max) // 2
    y_center = (y_min + y_max) // 2

    # handle grayscale frames
    if len(frame.shape) == 2 or frame.shape[2] == 1:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

    # calc gaze dir
    length = x_max - x_min
    dx = int(-length * np.sin(pitch) * np.cos(yaw))
    dy = int(-length * np.sin(yaw))

    # calc angular dev from camera
    deviation = np.sqrt(pitch**2 + yaw**2)
    
    # set color based on thresh
    if deviation <= attention_threshold:
        color = (0, 255, 0)  # green: looking at cam
        text = "Looking at Ad"
    else:
        color = (0, 0, 255)  # red: not looking
        text = "NOT looking at Ad"

    # draw attn status
    cv2.putText(frame, text, (x_min, y_min - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    point1 = (x_center, y_center)
    point2 = (x_center + dx, y_center + dy)

    # draw gaze dir
    cv2.circle(frame, (x_center, y_center), radius=4, color=color, thickness=-1)
    cv2.arrowedLine(
        frame,
        point1,
        point2,
        color=color,
        thickness=thickness,
        line_type=cv2.LINE_AA,
        tipLength=0.25
    )
    
    return deviation <= attention_threshold  # ret if looking at ad


def draw_bbox(image, bbox, color=(0, 255, 0), thickness=2, proportion=0.2):
    # get coords
    x_min, y_min, x_max, y_max = map(int, bbox[:4])

    width = x_max - x_min
    height = y_max - y_min

    corner_length = int(proportion * min(width, height))

    # draw rect
    cv2.rectangle(image, (x_min, y_min), (x_max, y_max), color, 1)

    # top-left
    cv2.line(image, (x_min, y_min), (x_min + corner_length, y_min), color, thickness)
    cv2.line(image, (x_min, y_min), (x_min, y_min + corner_length), color, thickness)

    # top-right
    cv2.line(image, (x_max, y_min), (x_max - corner_length, y_min), color, thickness)
    cv2.line(image, (x_max, y_min), (x_max, y_min + corner_length), color, thickness)

    # bottom-left
    cv2.line(image, (x_min, y_max), (x_min, y_max - corner_length), color, thickness)
    cv2.line(image, (x_min, y_max), (x_min + corner_length, y_max), color, thickness)

    # bottom-right
    cv2.line(image, (x_max, y_max), (x_max, y_max - corner_length), color, thickness)
    cv2.line(image, (x_max, y_max), (x_max - corner_length, y_max), color, thickness)


def draw_bbox_gaze(frame: np.ndarray, bbox, pitch, yaw, attention_threshold=0.20):
    """Draws bbox and gaze dir."""
    global looks_count, no_looks_count, total_faces
    
    # draw bbox
    draw_bbox(frame, bbox)
    
    # draw gaze and get attn state
    is_looking = draw_gaze(frame, bbox, pitch, yaw, attention_threshold)
    
    # update counters
    total_faces += 1
    if is_looking:
        looks_count += 1
    else:
        no_looks_count += 1
    
    return is_looking

def draw_stats(frame):
    """Draw stats in top right corner"""
    global percentage_queue
    
    height, width = frame.shape[:2]
    
    # calc percentage
    looking_percentage = 0
    if total_faces > 0:
        looking_percentage = (looks_count / total_faces) * 100
    
    # Add percentage to queue for writing
    percentage_queue.put(looking_percentage)
    
    # bg rect for readability
    cv2.rectangle(frame, (width-300, 0), (width, 120), (0, 0, 0), -1)
    
    # stats text
    y_pos = 30
    cv2.putText(frame, f"Total Faces: {total_faces}", 
                (width-290, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    y_pos += 30
    cv2.putText(frame, f"Looking Count: {looks_count}", 
                (width-290, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    y_pos += 30
    cv2.putText(frame, f"Not Looking: {no_looks_count}", 
                (width-290, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    
    y_pos += 30
    cv2.putText(frame, f"Looking %: {looking_percentage:.1f}%", 
                (width-290, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
