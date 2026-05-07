#
# Created on Thu Jan 21 11:27:22 2021
#
# @author: guiji
#
import re
from PIL import Image
from scipy import signal
import time
import numpy as np
import cv2
import multiprocessing.dummy as mp

video_time = []

class op:

    def __init__(self, caped_img2, wh, scrfd_detector, scrfd_predictor, hp, lm3d_std, img_size, driver_flag, target_face_id=0):
        self.manager = mp.Manager
        self.mp_dict = self.manager().dict()
        self.img_size = img_size
        self.target_size = self.img_size + int(self.img_size / 256.0) * 10
        for idx in caped_img2.keys():
            self.mp_dict[idx] = caped_img2[idx]
        self.wh = wh
        self.scrfd_detector = scrfd_detector
        self.scrfd_predictor = scrfd_predictor
        self.hp = hp
        self.pose_threshold = [[-70, 50], [-100, 100], [-70, 70]]
        self.driver_flag = driver_flag
        self.target_face_id = target_face_id  # 新增：记录目标脸ID
        self.no_face = []

    def show(self):
        for idx in self.mp_dict.keys():
            print(self.mp_dict[idx], idx)

    def get_max_face(self, face_boxes):
        if face_boxes.shape[0] == 1:
            return face_boxes[0].astype(int)

        # Return the box with the largest area
        return face_boxes[np.nanargmax(np.abs(face_boxes[:, 2] - face_boxes[:, 0]) * np.abs(face_boxes[:, 3] - face_boxes[:, 1]))].astype(int)


    def loc_detect_face(self, idx):
        loc_dict = self.mp_dict[idx]
        img = loc_dict['imgs_data']
        t0 = time.time()
        (face_boxes, _) = self.scrfd_detector.get_bboxes(img)
        (h, w) = img.shape[0:2]

        if face_boxes.shape[0] > 0:
            # 多脸模式：处理所有脸
            if self.target_face_id == -1:
                all_boxes_p = []
                for i in range(face_boxes.shape[0]):
                    (x1, y1, x2, y2, score) = face_boxes[i].astype(int)

                    # Expand bounding box
                    x1 = max(0, x1 - int((x2 - x1) * 0.1))
                    y1 = max(0, y1)
                    x2 = min(w, x2 + int((x2 - x1) * 0.1))
                    y2 = min(h, y2 + int((y2 - y1) * 0.1))

                    face_img = img[int(y1):int(y2), int(x1):int(x2)]
                    pots = self.scrfd_predictor.forward(face_img)[0]
                    landmarks = np.array([[x + x1, y + y1] for x, y in pots.astype(np.int32)])

                    (xmin, ymin, w_box, h_box) = cv2.boundingRect(np.array(landmarks))
                    x_c = xmin + w_box / 2.0
                    wh_ratio = w_box / h_box

                    # Calculate 3DMM bounding box
                    Xmin_3dmm = int(x_c - w_box / wh_ratio * 0.8)
                    Xmax_3dmm = int(x_c + w_box / wh_ratio * 0.8)
                    Ymin_3dmm = int(ymin - w_box / wh_ratio * 0.35)
                    Ymax_3dmm = int(ymin + w_box / wh_ratio * 1.25)

                    # Clamp coordinates
                    Xmin_3dmm = max(0, Xmin_3dmm)
                    Ymin_3dmm = max(0, Ymin_3dmm)
                    Xmax_3dmm = min(img.shape[1], Xmax_3dmm)
                    Ymax_3dmm = min(img.shape[0], Ymax_3dmm)

                    head_poses = self.hp.get_head_pose(img[int(Ymin_3dmm):int(Ymax_3dmm), int(Xmin_3dmm):int(Xmax_3dmm)])

                    # Check head pose
                    if head_poses[0] > self.pose_threshold[0][0] and head_poses[0] < self.pose_threshold[0][1] and \
                       head_poses[1] > self.pose_threshold[1][0] and head_poses[1] < self.pose_threshold[1][1] and \
                       head_poses[2] > self.pose_threshold[2][0] and head_poses[2] < self.pose_threshold[2][1]:
                        all_boxes_p.append(np.array((y1, y2, x1, x2)))
                    else:
                        print(f'脸 {i} 侧脸检测不通过，跳过该脸', head_poses)
                        # 不添加空数组，直接跳过无效脸
                        continue

                # 存储所有脸的bounding boxes
                loc_dict['bounding_box_p'] = all_boxes_p if len(all_boxes_p) > 0 else []

            # 单脸模式：只选择最大的脸
            else:
                (x1, y1, x2, y2, score) = self.get_max_face(face_boxes)

                # Expand bounding box
                x1 = max(0, x1 - int((x2 - x1) * 0.1))
                y1 = max(0, y1)
                x2 = min(w, x2 + int((x2 - x1) * 0.1))
                y2 = min(h, y2 + int((y2 - y1) * 0.1))

                face_img = img[int(y1):int(y2), int(x1):int(x2)]
                pots = self.scrfd_predictor.forward(face_img)[0]
                landmarks = np.array([ [x + x1, y + y1] for x, y in pots.astype(np.int32)])

                (xmin, ymin, w_box, h_box) = cv2.boundingRect(np.array(landmarks))
                x_c = xmin + w_box / 2.0
                wh = w_box / h_box

                # Calculate 3DMM bounding box
                Xmin_3dmm = int(x_c - w_box / wh * 0.8)
                Xmax_3dmm = int(x_c + w_box / wh * 0.8)
                Ymin_3dmm = int(ymin - w_box / wh * 0.35)
                Ymax_3dmm = int(ymin + w_box / wh * 1.25)

                # Clamp coordinates to image boundaries
                if Xmin_3dmm <= 0:
                    Xmin_3dmm = 0
                if Ymin_3dmm <= 0:
                    Ymin_3dmm = 0
                if Xmax_3dmm >= img.shape[1]:
                    Xmax_3dmm = img.shape[1]
                if Ymax_3dmm >= img.shape[0]:
                    Ymax_3dmm = img.shape[0]

                head_poses = self.hp.get_head_pose(img[int(Ymin_3dmm):int(Ymax_3dmm), int(Xmin_3dmm):int(Xmax_3dmm)])

                # Check if head pose is within acceptable thresholds
                if head_poses[0] > self.pose_threshold[0][0] and head_poses[0] < self.pose_threshold[0][1] and \
                   head_poses[1] > self.pose_threshold[1][0] and head_poses[1] < self.pose_threshold[1][1] and \
                   head_poses[2] > self.pose_threshold[2][0] and head_poses[2] < self.pose_threshold[2][1]:
                    loc_dict['bounding_box_p'] = np.array((y1, y2, x1, x2))
                else:
                    print('侧脸检测不通过', head_poses)
                    loc_dict['bounding_box_p'] = []
        else:
            loc_dict['bounding_box_p'] = []

        self.mp_dict[idx] = loc_dict

    def loc_crop_face(self, idx):
        loc_dict = self.mp_dict[idx]
        img = loc_dict['imgs_data']
        dets = self.mp_dict[idx]['bounding_box_p']

        # 多脸模式：target_face_id == -1
        if self.target_face_id == -1:
            # dets 是一个列表：[array([y1, y2, x1, x2]), array([...]), ...]
            if isinstance(dets, list) and len(dets) > 0:
                # 处理所有脸
                all_landmarks = []
                all_bounding_boxes = []
                all_crop_lms = []
                all_crop_imgs = []

                for face_det in dets:
                    # 检查是否有效脸
                    if len(face_det) == 4 and max(face_det) > 0:
                        # 获取landmarks
                        face_landmarks = self.scrfd_predictor.forward(img[int(face_det[0]):int(face_det[1]), int(face_det[2]):int(face_det[3])])[0]
                        landmarks = face_landmarks + np.array([face_det[2], face_det[0]])[np.newaxis, :]

                        (xmin, ymin, w, h) = cv2.boundingRect(np.array(landmarks).astype(np.int32))
                        x_c = xmin + w / 2.0

                        # Define cropping box
                        Xmin = int(x_c - w / self.wh * 0.75)
                        Xmax = int(x_c + w / self.wh * 0.75)
                        Ymin = int(ymin - w / self.wh * 0.15)
                        Ymax = int(ymin + w / self.wh * 1.35)

                        # Clamp
                        Xmin = max(0, Xmin)
                        Ymin = max(0, Ymin)
                        Xmax = min(img.shape[1], Xmax)
                        Ymax = min(img.shape[0], Ymax)

                        bounding_box = np.array([Ymin, Ymax, Xmin, Xmax])

                        # Normalize landmarks
                        lm_crop = np.zeros(landmarks.shape)
                        lm_crop[..., 0] = self.target_size * (landmarks[..., 0] - Xmin) / (Xmax - Xmin)
                        lm_crop[..., 1] = self.target_size * (landmarks[..., 1] - Ymin) / (Ymax - Ymin)

                        # Crop and resize image（与单脸模式相同）
                        img_crop = img[Ymin:Ymax, Xmin:Xmax]
                        if self.driver_flag:
                            img_crop = cv2.cvtColor(cv2.resize(img_crop, (self.target_size, self.target_size), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
                        else:
                            img_crop = cv2.resize(img_crop, (self.target_size, self.target_size), interpolation=cv2.INTER_CUBIC)

                        all_landmarks.append(lm_crop)
                        all_bounding_boxes.append(bounding_box)
                        all_crop_lms.append(lm_crop)
                        all_crop_imgs.append(img_crop)

                if len(all_landmarks) > 0:
                    loc_dict['landmarks'] = all_landmarks
                    loc_dict['bounding_box'] = all_bounding_boxes
                    loc_dict['crop_lm'] = all_crop_lms
                    loc_dict['crop_img'] = all_crop_imgs
                else:
                    self.no_face.append(idx)
                    loc_dict['bounding_box_p'] = []
            else:
                # 没有检测到脸
                self.no_face.append(idx)
                loc_dict['bounding_box_p'] = []

        # 单脸模式：只处理一张脸
        else:
            # Handle case where no valid face was detected
            if len(dets) == 0 or (not isinstance(dets, list) and max(dets) == 0):
                self.no_face.append(idx)
                dets = [0, 100, 0, 100]
                self.mp_dict[idx]['bounding_box_p'] = [0, 0, 0, 0]

            if len(dets) > 0:
                t0 = time.time()
                # 单脸模式下，dets 是 np.array((y1, y2, x1, x2))
                det = dets[0] if isinstance(dets, list) else dets

                face_landmarks = self.scrfd_predictor.forward(img[int(det[0]):int(det[1]), int(det[2]):int(det[3])])[0]
                landmarks = face_landmarks + np.array([det[2], det[0]])[np.newaxis, :]
                loc_dict['landmarks'] = landmarks

                (xmin, ymin, w, h) = cv2.boundingRect(np.array(landmarks).astype(np.int32))
                x_c = xmin + w / 2.0

                # Define cropping box based on landmarks and aspect ratio
                Xmin = int(x_c - w / self.wh * 0.75)
                Xmax = int(x_c + w / self.wh * 0.75)
                Ymin = int(ymin - w / self.wh * 0.15)
                Ymax = int(ymin + w / self.wh * 1.35)

                # Clamp coordinates
                if Xmin <= 0: Xmin = 0
                if Ymin <= 0: Ymin = 0
                if Xmax >= img.shape[1]: Xmax = img.shape[1]
                if Ymax >= img.shape[0]: Ymax = img.shape[0]

                loc_dict['bounding_box'] = np.array([Ymin, Ymax, Xmin, Xmax])

                # Normalize landmarks to the cropped image
                lm_crop = np.zeros(landmarks.shape)
                lm_crop[..., 0] = self.target_size * (landmarks[..., 0] - Xmin) / (Xmax - Xmin)
                lm_crop[..., 1] = self.target_size * (landmarks[..., 1] - Ymin) / (Ymax - Ymin)

                # Crop and resize image
            img_crop = img[Ymin:Ymax, Xmin:Xmax]
            if self.driver_flag:
                img_crop = cv2.cvtColor(cv2.resize(img_crop, (self.target_size, self.target_size), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
            else:
                img_crop = cv2.resize(img_crop, (self.target_size, self.target_size), interpolation=cv2.INTER_CUBIC)
            
            loc_dict['crop_lm'] = lm_crop
            loc_dict['crop_img'] = img_crop
            self.mp_dict[idx] = loc_dict

    def smooth_(self):
        # 检查是否为多脸模式
        is_multi_face = False
        if len(self.mp_dict) > 0:
            first_bbox_p = list(self.mp_dict.values())[0].get('bounding_box_p', None)
            if first_bbox_p is not None and isinstance(first_bbox_p, list):
                is_multi_face = True

        # 多脸模式：不对 bounding_box_p 进行平滑（因为多脸模式下每帧脸的数量可能不同）
        # 改为对后续展开后的数据进行平滑
        if is_multi_face:
            return

        # 单脸模式：原有的平滑逻辑
        max_len = np.array([it for it in self.mp_dict.keys()]).max()
        bbx_smooth = np.zeros((max_len, 4))
        keylist = list(self.mp_dict.keys())
        keylist.sort()

        # Fill in missing bounding boxes with the previous one
        for it in keylist:
            if len(self.mp_dict[it]['bounding_box_p']) != 4:
                bbx_smooth[it - 1, :] = bbx_smooth[it - 2, :]
                continue
            bbx_smooth[it - 1, :] = self.mp_dict[it]['bounding_box_p']

        # Apply a simple moving average filter
        conv_core = np.ones((5, 1)) / 5.0
        bbx_smooth2 = signal.convolve2d(bbx_smooth, conv_core, boundary='symm', mode='same')

        # Replace original with smoothed if the difference is small
        bbx_smooth_dif = np.where(np.abs(bbx_smooth2 - bbx_smooth).sum(1) > 12)[0]
        bbx_smooth3 = bbx_smooth + 0
        bbx_smooth3[bbx_smooth_dif] = bbx_smooth[bbx_smooth_dif]

        bbx_smooth4 = signal.convolve2d(bbx_smooth3, conv_core, boundary='symm', mode='same')

        # Update the dictionary with smoothed boxes
        for it in self.mp_dict:
            loc_dict = self.mp_dict[it]
            loc_dict['bounding_box_p'] = bbx_smooth4[it - 1, :]
            self.mp_dict[it] = loc_dict


    def flow(self):
        for idx in self.mp_dict.keys():
            self.loc_detect_face(idx)
        for idx in self.mp_dict.keys():
            self.loc_crop_face(idx)