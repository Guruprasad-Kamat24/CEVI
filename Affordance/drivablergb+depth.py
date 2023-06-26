# -*- coding: utf-8 -*-
"""drivablergb+depth.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1w_dBcgvt7N2vOKvzloLV19pkZmBTslEP
"""

import numpy as np
import os
from torch.utils.data import Dataset
import torch
from PIL import Image
import matplotlib.pyplot as plt
from albumentations.pytorch import ToTensorV2
import albumentations as A
import cv2
from skimage import io
from glob import glob
from tqdm import tqdm
from tqdm import tqdm
from torchvision import transforms
import torch.nn as nn
from torch.optim import Adam
from tqdm import tqdm

class LyftUdacity(Dataset):
    def __init__(self,image_dir,depth_dir,seg_dir,transform = None,tm = None):
        self.transforms = transform
        self.tm = tm
        
        self.images,self.depth,self.masks = [],[],[]
        
        for idx in range(0,2975):
            x = str(idx)
            temp_r_path = image_dir + '/' + 'gfg_dummy_pic' + x + '.png'
            self.images.append(temp_r_path)

        for idx in range(0,2975):
            x1 = str(idx)
            temp_s_path = seg_dir + '/' + 'gfg_dummy_pic' + x1 + '.png'
            self.masks.append(temp_s_path)

        for idx in range(0,2975):
            x2 = str(idx)
            temp_r_path = depth_dir + '/' + 'gfg_dummy_pic' + x2 + '.png'
            self.depth.append(temp_r_path)
        
          
          
       
    def __len__(self):
        return len(self.images)
    def __getitem__(self,index):
        
        img = np.array(Image.open(self.images[index]))
        depth= np.array(Image.open(self.depth[index]))
        dim = (256,256)
        img = cv2.resize(img, dim, interpolation = cv2.INTER_AREA)
        depth= cv2.resize(depth.astype(float), (256,256), interpolation = cv2.INTER_AREA)
        depth = depth.astype('uint8')
        cat = cv2.merge((img,depth))
        # img.resize((427,561),refcheck=False)

        mask = np.array(Image.open(self.masks[index]))
        mask= cv2.resize(mask, dim, interpolation = cv2.INTER_AREA)
        # mask.resize((256,256))
        # mask.resize((256,256),refcheck=False)
        # mask= cv2.resize(mask, dim, interpolation = cv2.INTER_AREA)
      
        # mask[mask > 128.0] = 1
        # mask[mask <= 128.0] = 0
      
        # mask = torch.tensor(mask)
        
        # mask = torch.from_numpy(mask)
        if self.transforms is not None:
            img = self.transforms(cat)
          
            # mask = self.transforms(mask)           
            
           # mask = torch.max(mask,dim=2)[0]
        return img,mask

image_dir="/content/drive/MyDrive/Cityscape/RGB"
depth_dir="/content/drive/MyDrive/Cityscape/DEPTH"
seg_dir="/content/drive/MyDrive/Cityscape/NEW_MASK"

t1 = transforms.Compose([
    # this operation was done, to make Image size compatible with AlexNet Model
    #transforms.Resize((527,527)),
    
    # To focus on only primary component of Image
   
    transforms.ToTensor(),
    # To nullify dominance of one of Color channel
    # transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5))
])

tm = A.Compose([
    A.Resize(256,256),
    A.augmentations.transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)),
    ToTensorV2()
])

def get_images(image_dir,depth_dir,seg_dir,transform = None,tm = None,batch_size=8,shuffle=True,pin_memory=False):
    data = LyftUdacity(image_dir,depth_dir,seg_dir,transform = t1,tm =tm)
    train_size = int(0.8 * data.__len__())
    test_size = data.__len__() - train_size
    train_dataset, test_dataset = torch.utils.data.random_split(data, [train_size, test_size])
    train_batch = torch.utils.data.DataLoader(train_dataset, batch_size=batch_size, shuffle=shuffle, pin_memory=pin_memory,num_workers=0)
    test_batch = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=shuffle, pin_memory=pin_memory,num_workers=0)
    return train_batch,test_batch

train_batch,test_batch = get_images(image_dir,depth_dir,seg_dir,batch_size=8)

class encoding_block(nn.Module):
    def __init__(self,in_channels, out_channels):
        super(encoding_block,self).__init__()
        model = []
        model.append(nn.Conv2d(in_channels, out_channels, 3, 1, 1, bias=False))
        model.append(nn.BatchNorm2d(out_channels))
        model.append(nn.ReLU(inplace=True))
        model.append(nn.Conv2d(out_channels, out_channels, 3, 1, 1, bias=False))
        model.append(nn.BatchNorm2d(out_channels))
        model.append(nn.ReLU(inplace=True))
        self.conv = nn.Sequential(*model)
    def forward(self, x):
        return self.conv(x)

class unet_model(nn.Module):
    def __init__(self,out_channels=2,features=[64, 128, 256, 512]):
        super(unet_model,self).__init__()
        self.pool = nn.MaxPool2d(kernel_size=(2,2),stride=(2,2))
        self.conv1 = encoding_block(4,features[0])
        self.conv2 = encoding_block(features[0],features[1])
        self.conv3 = encoding_block(features[1],features[2])
        self.conv4 = encoding_block(features[2],features[3])
        self.conv5 = encoding_block(features[3]*2,features[3])
        self.conv6 = encoding_block(features[3],features[2])
        self.conv7 = encoding_block(features[2],features[1])
        self.conv8 = encoding_block(features[1],features[0])        
        self.tconv1 = nn.ConvTranspose2d(features[-1]*2, features[-1], kernel_size=2, stride=2)
        self.tconv2 = nn.ConvTranspose2d(features[-1], features[-2], kernel_size=2, stride=2)
        self.tconv3 = nn.ConvTranspose2d(features[-2], features[-3], kernel_size=2, stride=2)
        self.tconv4 = nn.ConvTranspose2d(features[-3], features[-4], kernel_size=2, stride=2)        
        self.bottleneck = encoding_block(features[3],features[3]*2)
        self.final_layer = nn.Conv2d(features[0],out_channels,kernel_size=1)
    def forward(self,x):
        skip_connections = []
        x = self.conv1(x)
        skip_connections.append(x)
        x = self.pool(x)
        x = self.conv2(x)
        skip_connections.append(x)
        x = self.pool(x)
        x = self.conv3(x)
        skip_connections.append(x)
        x = self.pool(x)
        x = self.conv4(x)
        skip_connections.append(x)
        x = self.pool(x)
        x = self.bottleneck(x)
        skip_connections = skip_connections[::-1]
        x = self.tconv1(x)
        x = torch.cat((skip_connections[0], x), dim=1)
        x = self.conv5(x)
        x = self.tconv2(x)
        x = torch.cat((skip_connections[1], x), dim=1)
        x = self.conv6(x)
        x = self.tconv3(x)
        x = torch.cat((skip_connections[2], x), dim=1)
        x = self.conv7(x)        
        x = self.tconv4(x)
        x = torch.cat((skip_connections[3], x), dim=1)
        x = self.conv8(x)
        x = self.final_layer(x)
        return x

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

model = unet_model().to(DEVICE)

torch.backends.cudnn.enabled=True

LEARNING_RATE = 1e-4
num_epochs = 100

loss_fn = nn.CrossEntropyLoss()
optimizer = Adam(model.parameters(), lr=LEARNING_RATE)

def check_accuracy(loader, model):
    num_correct = 0
    num_pixels = 0
    dice_score = 0
    model.eval()

    with torch.no_grad():
        for x, y in loader:
            x = x.to(DEVICE)
            y = y.to(DEVICE)
            softmax = nn.Softmax(dim=1)
            preds = torch.argmax(softmax(model(x)),axis=1)
            num_correct += (preds == y).sum()
            num_pixels += torch.numel(preds)
            dice_score += (2 * (preds * y).sum()) / ((preds + y).sum() + 1e-8)

    # print(f"Got {num_correct}/{num_pixels} with acc {num_correct/num_pixels*100:.2f}")
    # print(f"Dice score: {dice_score/len(loader)}")
    return num_correct/num_pixels*100
    model.train()

x=0
prev_acc=0
for epoch in range(num_epochs):
    loop = tqdm(enumerate(train_batch),total=len(train_batch))
    for batch_idx, (data, targets) in loop:
        data = data.to(DEVICE)
        targets = targets.to(DEVICE)
        targets = targets.type(torch.long)
        # forward
        predictions = model(data)
        loss = loss_fn(predictions, targets)
        # backward
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        # update tqdm loop
        loop.set_postfix(loss=loss.item())
    if(x%2 == 0):
        cur_acc = check_accuracy(train_batch, model)
        if(cur_acc >prev_acc):
            prev_acc = cur_acc
            PATH ="modelsem"+str(x)+".pth"
            torch.save(model, PATH)
        print(cur_acc)
    x = x+1
    print(x)