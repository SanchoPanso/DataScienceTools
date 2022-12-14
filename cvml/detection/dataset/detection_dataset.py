import os
import sys
import cv2
import random
import math
import numpy as np
from abc import ABC
from typing import List, Set, Dict, Callable
from enum import Enum
import logging

import time
from cvml.core.bounding_box import BoundingBox
from cvml.detection.dataset.annotation_converter import AnnotationConverter, write_yolo_labels, read_yolo_labels
from cvml.detection.dataset.annotation import Annotation
from cvml.detection.dataset.image_source import ImageSource


# class LabeledImage:
#     def __init__(self,
#                  image_source: ImageSource = None,
#                  bboxes: List[BoundingBox] = None,
#                  name: str = None):

#         self.image_source = image_source
#         self.bboxes = bboxes or []
#         self.name = name or image_source.get_name()

#     def save(self, images_dir: str = None, labels_dir: str = None):
#         if images_dir is not None and self.image_source is not None:
#             self.image_source.save(os.path.join(images_dir, self.name + '.jpg'))

#         if labels_dir is not None:
#             write_yolo_labels(os.path.join(labels_dir, self.name + '.txt'),
#                               self.bboxes)
        

class DetectionDataset:
    """
    Class of dataset, representing sets of labeled images with bounding boxes, 
    which are used in detection tasks.
    """

    def __init__(self, 
                 image_sources: List[ImageSource] = None,
                 annotation: Annotation = None, 
                 samples: Dict[str, List[int]] = None):
        """Constructor

        :param image_sources: list image sources, representing images, that will be placed in dataset, defaults to None
        :param annotation: annotation of images, represented by image sources, defaults to None
        :param samples: dict of lists of indexes of images, that corresponds to a specific set, defaults to None
        """
        
        self.image_sources = image_sources or []
        self.annotation = annotation or Annotation()
        self.samples = samples or {}
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
    

    def __len__(self):
        return len(self.image_sources)

    def __getitem__(self, item):
        return self.image_sources[item]

    def __add__(self, other):
        
        # Addition of image sources
        sum_image_sources = self.image_sources + other.image_sources
        
        # Addition of annotation
        sum_annotation = self.annotation + other.annotation
        
        # Addition of samples
        self_sample_names = set(self.samples.keys())
        other_sample_names = set(other.samples.keys())
        
        # sum_sample_names - union of two sample names 
        sum_sample_names = self_sample_names or other_sample_names
        sum_samples = {}
        
        # In new samples self indexes remain their values, others - are addicted with number of images in self
        # (other images addict to the end of common list) 
        for name in sum_sample_names:
            sum_samples[name] = []
            if name in self_sample_names:
                sum_samples[name] += self.samples[name]
            if name in other_sample_names:
                sum_samples[name] += list(map(lambda x: x + len(self), other.samples[name]))
        
        return DetectionDataset(sum_image_sources, sum_annotation, sum_samples)

    def update(self, 
               image_sources: List[ImageSource] = None,
               annotation: Annotation = None, 
               samples: Dict[str, List[int]] = None):
        """DEPRECATED

        :param image_sources: _description_, defaults to None
        :param annotation: _description_, defaults to None
        :param samples: _description_, defaults to None
        """
        image_sources = image_sources or []
        annotation = annotation or Annotation()

        self.image_sources = image_sources or []
        self.annotation = annotation or Annotation()
        self.samples = samples or {}
        
        raise DeprecationWarning
    
    def rename(self, rename_callback: Callable):
        
        for i in range(len(self.image_sources)):
            
            # Rename image source
            old_name = self.image_sources[i].name
            new_name = rename_callback(self.image_sources[i].name)
            self.image_sources[i].name = new_name
            
            # Rename in bbox_map
            bboxes = self.annotation.bbox_map[old_name]
            self.annotation.bbox_map.pop(old_name)
            self.annotation.bbox_map[new_name] = bboxes
            
            # Rename in bboxes
            for bb in self.annotation.bbox_map[new_name]:
                bb._image_name = rename_callback(bb._image_name)

    def split_by_proportions(self, proportions: dict):
        all_idx = [i for i in range(len(self.image_sources))]
        random.shuffle(all_idx)

        length = len(self.image_sources)
        split_start_idx = 0
        split_end_idx = 0

        # Reset current split indexes
        self.samples = {}

        num_of_names = len(proportions.keys())

        for i, split_name in enumerate(proportions.keys()):
            split_end_idx += math.ceil(proportions[split_name] * length)
            self.samples[split_name] = all_idx[split_start_idx: split_end_idx]
            split_start_idx = split_end_idx

            if i + 1 == num_of_names and split_end_idx < len(all_idx):
                self.samples[split_name] += all_idx[split_end_idx: len(all_idx)]
        
        # logging
        message = "In dataset the following splits was created: "
        for i, split_name in enumerate(self.samples.keys()):
            message += f"{split_name}({len(self.samples[split_name])})"
            if i != len(self.samples.keys()) - 1:
                message += ", "
        self.logger.info(message)

    def split_by_dataset(self, yolo_dataset_path: str):

        # Define names of splits as dirnames in dataset directory
        split_names = [name for name in os.listdir(yolo_dataset_path)
                       if os.path.isdir(os.path.join(yolo_dataset_path, name))]

        # Reset current split indexes
        self.samples = {}

        for split_name in split_names:

            # Place names of orig dataset split in set structure
            orig_dataset_files = os.listdir(os.path.join(yolo_dataset_path, split_name, 'labels'))
            orig_names_set = set()

            for file in orig_dataset_files:
                name, ext = os.path.splitext(file)
                orig_names_set.add(name)

            # If new_name in orig dataset split then update split indexes of current dataset
            self.samples[split_name] = []
            for i, labeled_image in enumerate(self.labeled_images):
                new_name = labeled_image.name
                if new_name in orig_names_set:
                    self.samples[split_name].append(i)

    def install(self, 
                dataset_path: str, 
                install_images: bool = True, 
                install_labels: bool = True, 
                install_annotations: bool = True, 
                install_description: bool = True):
        
        for split_name in self.samples.keys():
            split_idx = self.samples[split_name]    
            
            if install_images:
                images_dir = os.path.join(dataset_path, split_name, 'images')
                os.makedirs(images_dir, exist_ok=True)
                
                for i in split_idx:
                    image_source = self.image_sources[i] 
                    image_source.save(os.path.join(images_dir, image_source.name + '.jpg'))                
                    self.logger.info(f"In split \"{split_name}\" image \"{self.image_sources[i].name}\" is processed")
                self.logger.info(f"In split \"{split_name}\" installing images is complete")

            if install_labels:
                labels_dir = os.path.join(dataset_path, split_name, 'labels')
                os.makedirs(labels_dir, exist_ok=True)
                sample_annotation = self._get_sample_annotation(split_name)
                AnnotationConverter.write_yolo(sample_annotation, labels_dir)
                self.logger.info(f"In split \"{split_name}\" installing labels is complete")
            
            if install_annotations:
                annotation_dir = os.path.join(dataset_path, split_name, 'annotations')
                os.makedirs(annotation_dir, exist_ok=True)
                coco_path = os.path.join(annotation_dir, 'data.json')
                sample_annotation = self._get_sample_annotation(split_name)
                AnnotationConverter.write_coco(sample_annotation, coco_path)
                self.logger.info(f"In split \"{split_name}\" installing annotation is complete")
            
            if install_description:
                self._write_description(os.path.join(dataset_path, 'data.yaml'))
                self.logger.info(f"In split \"{split_name}\" installing description is complete")
    
    def exclude_by_names(self, excluding_names: Set[str], splits: List[str]):
        
        for split in splits:
            for i in range(len(self.samples[split]) - 1, -1, -1):
                idx = self.samples[split][i]
                labeled_image = self.labeled_images[idx]
                new_name = labeled_image.name

                if new_name in excluding_names:
                    self.samples[split].pop(i)
    
    def _get_sample_annotation(self, sample_name: str) -> Annotation:
        sample_classes = self.annotation.classes
        sample_bbox_map = {}
        
        for i in self.samples[sample_name]:
            image_source = self.image_sources[i]
            name = image_source.name
            sample_bbox_map[name] = self.annotation.bbox_map[name]
        
        sample_annotation = Annotation(sample_classes, sample_bbox_map)
        return sample_annotation
    
    def _write_description(self, path: str):
        dataset_name = os.path.split(os.path.dirname(path))[-1]
        text = f"train: /content/{dataset_name}/train/images\n" \
               f"val: /content/{dataset_name}/valid/images\n\n" \
               f"nc: {len(self.annotation.classes)}\n" \
               f"names: {self.annotation.classes}"
        with open(path, 'w') as f:
            f.write(text)
        




