# -*- coding: utf-8 -*-
"""Copia de Traffic.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1gH-4wJ5bnss0DbC9gz0MPRNAucHlthiU
"""

# Commented out IPython magic to ensure Python compatibility.
# %cd
!rm -rf ~/Mask_RCNN
!git clone --quiet https://github.com/matterport/Mask_RCNN.git
# %cd ~/Mask_RCNN
!ls mrcnn

!pip install -q PyDrive
!pip install -r requirements.txt
!python setup.py install


from mrcnn.config import Config
from mrcnn import model as modellib, utils
from samples import coco

import os
import sys
import json
import datetime
import numpy as np
import skimage.draw
import pandas as pd
from tqdm import tqdm
from multiprocessing.dummy import Pool as ThreadPool
import imgaug
from os.path import isfile, join
from os import listdir
import shutil

# Drive path
DRIVE_DIR = "/content/drive"
# Root directory of the project
ROOT_DIR = "/content/drive/My Drive/data/"
# Where we will store images
IMAGE_DIR = ROOT_DIR + "images2"
# Path to trained weights file
COCO_WEIGHTS_PATH = ROOT_DIR + "mask_rcnn_coco.h5"
# Directory to save logs and model checkpoints, if not provided
DEFAULT_LOGS_DIR = "~/Mask_RCNN/logs"
# ANNOTATIONS
ANNO_DIR = ROOT_DIR + "train-annotations-object-segmentation.csv"
# MODEL_DIR
MODEL_DIR = "/content/logs"
# MASKS 
MASK_DIR = ROOT_DIR + "masks/"

from os import scandir

def ls2(path): 
    return [obj.name for obj in scandir(path) if obj.is_file()]

from google.colab import drive
drive.mount(DRIVE_DIR,force_remount = True)

# Create neccesary files
#!rm -rf '/content/images' 
#!cp -r "/content/drive/My Drive/data/images" "/content/"
#!cp "/content/drive/My Drive/data/mask_rcnn_coco.h5" "/content/"
#!cp "/content/drive/My Drive/data/train-annotations-object-segmentation.csv" -d "/content/"
!mkdir "/content/logs"
#! unzip "/content/drive/My Drive/train-annotations-object-segmentation.zip" -d "/content/"
#! unzip "/content/drive/My \Drive/images.tar.gz" -d "/content/"

# We keep only the part of the CSV that we want. (Only the imgs we have)
files = ls2(IMAGE_DIR)
ids   = [os.path.splitext(f)[0] for f in files]
f = pd.read_csv(ANNO_DIR)
new_csv = f.loc[f['ImageID'].isin(ids)]


# Esta función descomprime images.zip en el directorio
#! unzip /content/drive/My\ Drive/train-annotations-object-segmentation.zip -d /content

class TrafficConfig(Config):
    """Configuration for training on the birds dataset.
    Derives from the base Config class and overrides values specific
    to the birds dataset.
    """
    # Give the configuration a recognizable name
    NAME = "traffic"

    # Train on 1 GPU and 8 images per GPU. We can put multiple images on each
    # GPU because the images are small. Batch size is 8 (GPUs * images/GPU).
    GPU_COUNT = 1
    IMAGES_PER_GPU = 2

    # Number of classes (including background)
    NUM_CLASSES = 1 + 4  # background + Traffic Lights + People + Cars + Traffic Signs

    # Use small images for faster training. Set the limits of the small side
    # the large side, and that determines the image shape.
    IMAGE_RESIZE_MODE = "square"
    IMAGE_MIN_DIM = 1024
    IMAGE_MAX_DIM = 1024
    # Training steps per epoch
    STEPS_PER_EPOCH = 250

    # Nº of steps at the end of training
    VALIDATION_STEPS = 25

    # Backbone. Resnet50 makes net faster
    BACKBONE = "resnet50"

    LEARNING_RATE = 0.01

config = TrafficConfig()
config.display()

def class_to_ind(c):
      if c == "/m/01g317":
        return 1
      elif c == "/m/015qff":
        return 2
      elif c == "/m/0k4j":
        return 3
      elif c == "/m/01mqdt":
        return 4
      else:
        return -1

class TrafficDataset(utils.Dataset):

    def load_dataset(self, dataset_dir, subset,f):
        "Add the images to the dataset"
        name_num = [["Person",['/m/01g317']],["TrafficLight",['/m/015qff']],["Car",['/m/0k4j']],["TrafficSign",['/m/01mqdt']]]
        # Add classes
        for i,clase in enumerate(name_num):
          self.add_class("traffic", class_to_ind(clase[1][0]), clase[0])

        # Add images 
        # Cojo todas las filas que tengan una clase de las cuales estudiamos
        u = f.loc[f['LabelName'].isin([clase[1][0] for clase in name_num])]
        # Cojo todos los ids de las imagenes y elimino los duplicados
        # Para cada ID
        for i,image_id in enumerate(subset):
          # Cojo las filas en las que aparece el ID
          datos_imagen = u.loc[u['ImageID'].isin([image_id])]
          image_dir = "{}/{}.jpg".format(dataset_dir, image_id)
          image = skimage.io.imread(image_dir)
          height, width = image.shape[:2]
          self.add_image(
                "traffic",
                image_id = i,  # use file name as a unique image id
                image_name = image_id,
                path=image_dir,
                clases = [class_to_ind(clase) for clase in datos_imagen['LabelName']],
                path_masks = [path for path in datos_imagen['MaskPath']])
 
    def load_mask(self, image_id):
        """Generate instance masks for an image.
        Returns:
        masks: A bool array of shape [height, width, instance count] with
            one mask per instance.
        class_ids: a 1D array of class IDs of the instance masks.
        """
        info = self.image_info[image_id]

        mask = []
        clases = []
        for i, p in enumerate(info["path_masks"]):
            #clases.append(class_to_ind(info['clases'][i]))
            mask_ = skimage.io.imread(MASK_DIR + p,True)
            mask_ = np.where(mask_ > 128, 1, 0)
            # Fill holes in the mask
            #mask_ = binary_fill_holes(mask_).astype(np.int32)
            # Add mask only if its area is larger than one pixel
            if np.sum(mask_) >= 1:
                mask.append(np.squeeze(mask_))

        mask = np.stack(mask, axis=-1)

        return mask.astype(np.uint8), np.array(info['clases'],dtype=np.int8)

        """
        #Occlusions
        occlusion = np.logical_not(finalmask[:, :, -1]).astype(np.uint8)
        for i in range(count-2, -1, -1):
            finalmask[:, :, i] = finalmask[:, :, i] * occlusion
            occlusion = np.logical_and(occlusion, np.logical_not(finalmask[:, :, i]))

        # Return mask, and array of class IDs of each instance. Since we have
        # one class ID, we return an array of ones
        return finalmask, class_ids
        """

    def load_image(self, image_id):
        """Load images according to the given image ID."""
        info = self.image_info[image_id]
        image = skimage.io.imread(info['path'])
        if len(image.shape)==2:
          image = skimage.color.gray2rgb(image)
        return image

    def image_reference(self, image_id):
        """Return the path of the image."""
        info = self.image_info[image_id]
        if info["source"] == "traffic":
            return info["path"]
        else:
            super(self.__class__, self).image_reference(image_id)

model = modellib.MaskRCNN(mode="training", config=config,
                                  model_dir=MODEL_DIR)

# Cargamos los pesos de Coco ya preentrenado
model.load_weights(COCO_WEIGHTS_PATH, by_name=True,
                    exclude=["mrcnn_class_logits", "mrcnn_bbox_fc",
                                "mrcnn_bbox", "mrcnn_mask"])

from shutil import copyfile
import random

# Here we make temp dirs for imgs
#! mkdir /content/temp_train
#! mkdir /content/temp_val
#TRAIN_DIR = "/content/temp_train"
#VAL_DIR   = "/content/temp_val"

# Pre-known
num_imgs = 793
n_all_imgs = 220
n_train_imgs = 200
n_val_imgs = 20


# 1. Select 600 images
all_index = random.sample(range(num_imgs), n_all_imgs)
# 2. Split in 500-100
train_index = random.sample(all_index,n_train_imgs)
val_index = [i for i in all_index + train_index if i not in all_index or i not in train_index]
#val_index = list(set(all_index) - set(train_index))
# For each element in each set, copy it in directory
trainID = [new_csv.iloc[ind]['ImageID'] for ind in train_index]

valID = [new_csv.iloc[ind]['ImageID'] for ind in val_index]

# Set Dataset
# Set train
dataset_train = TrafficDataset()

informacion_imagenes = pd.read_csv(ANNO_DIR)
dataset_train.load_dataset(IMAGE_DIR, trainID, new_csv)
dataset_train.prepare()

# Validation dataset
dataset_val = TrafficDataset()
dataset_val.load_dataset(IMAGE_DIR, valID, new_csv)
dataset_val.prepare()

from mrcnn import visualize
# Inspect the train dataset
print("Image Count: {}".format(len(dataset_val.image_ids)))
print("Class Count: {}".format(dataset_val.num_classes))
for i, info in enumerate(dataset_val.class_info):
    print("{:3}. {:50}".format(i, info['name']))
  
# Load and display random samples
image_ids = np.random.choice(dataset_val.image_ids, 5)
for image_id in image_ids:
    image = dataset_val.load_image(image_id)
    mask, class_ids = dataset_val.load_mask(image_id)
    visualize.display_top_masks(image, mask, class_ids,
                                dataset_val.class_names)

# Image Augmentation
# Right/Left flip 50% of the time
augmentation = imgaug.augmenters.Fliplr(0.5)

# *** This training schedule is an example. Update to your needs ***

# Training - Stage 1
print("Training network heads")
model.train(dataset_train, dataset_val,
            learning_rate=config.LEARNING_RATE / 10,
            epochs=10,
            layers='heads',
            augmentation=augmentation)

model.keras_model.save_weights(MODEL_DIR+"w2.h5")

# Training - Stage 2
# Finetune layers from ResNet stage 4 and up
#print("Fine tune Resnet stage 4 and up")
model.train(dataset_train, dataset_val,
           learning_rate=config.LEARNING_RATE / 10,
           epochs=5,
           layers='4+',
           augmentation=augmentation)

model.keras_model.save_weights(MODEL_DIR+"w3.h5")

# Training - Stage 3
# Fine tune all layers
#print("Fine tune all layers")
#model.train(dataset_train, dataset_val,
#           learning_rate=config.LEARNING_RATE / 10,
#            epochs=5,
#            layers='all',
#            augmentation=augmentation)

class InferenceConfig(TrafficConfig):
            # Set batch size to 1 since we'll be running inference on
            # one image at a time. Batch size = GPU_COUNT * IMAGES_PER_GPU
            GPU_COUNT = 1
            IMAGES_PER_GPU = 1
            DETECTION_MIN_CONFIDENCE = 0
config = InferenceConfig()
config.display()

modelI = modellib.MaskRCNN(mode="inference", config=config,
                                  model_dir=DEFAULT_LOGS_DIR)
modelI.load_weights(model.find_last(),True)

fid = np.random.choice(dataset_train.image_ids, 1)
original_image = dataset_train.load_image(fid[0])
results = modelI.detect([original_image], verbose=1)

r = results[0]
visualize.display_instances(original_image, r['rois'], r['masks'], r['class_ids'], 
                            dataset_val.class_names, r['scores'])

# Compute mAP
#APs_05: IoU = 0.5
#APs_all: IoU from 0.5-0.95 with increments of 0.05
image_ids = np.random.choice(dataset_val.image_ids, 5)
APs_05 = []
APs_all = []

for i, image_id in enumerate(image_ids):
    # Load images and ground truth data
    image, image_meta, gt_class_id, gt_bbox, gt_mask = \
        modellib.load_image_gt(dataset_val, modelI,
                               image_id, use_mini_mask=False)
    molded_images = np.expand_dims(modellib.mold_image(image, inference_config), 0)
    # Run object detection
    results = model.detect([image], verbose=0)
    r = results[0]
    # Compute AP
    AP_05, precisions, recalls, overlaps = \
        utils.compute_ap(gt_bbox, gt_class_id, gt_mask,
                         r["rois"], r["class_ids"], r["scores"], r['masks'])
    APs_05.append(AP_05)

    AP_all = \
        utils.compute_ap_range(gt_bbox, gt_class_id, gt_mask,
                         r["rois"], r["class_ids"], r["scores"], r['masks'])
    APs_all.append(AP_all)
    print("image " + str(i) + ": AP_05 = " + str(AP_05) + ", AP_all = " + str(AP_all))

print("mAP: ", np.mean(APs_05))
print("mAP: ", np.mean(APs_all))

