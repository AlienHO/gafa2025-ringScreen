#!/usr/bin/env python3
import cv2
import numpy as np
import time
import random
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from deepface import DeepFace
from mtcnn import MTCNN
from pythonosc import udp_client
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def download_file_with_retry(url, save_path, max_retries=3):
    session = requests.Session()
    retries = Retry(total=max_retries, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))
    
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        with open(save_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        logging.error(f"下载失败: {e}")
        return False

# 检查并下载情绪模型
model_path = Path(__file__).parent / 'models' / 'facial_expression_model_weights.h5'
if not model_path.exists():
    os.makedirs(model_path.parent, exist_ok=True)
    model_url = "https://github.com/serengil/deepface_models/releases/download/v1.0/facial_expression_model_weights.h5"
    if not download_file_with_retry(model_url, str(model_path)):
        logging.error("模型下载失败，请检查网络连接或手动下载。")
        exit(1)

# ---------------- 配置 ----------------
CAMERA_ID = 0
TARGET_W = 1280
TARGET_H = 720
SAMPLE_INTERVAL = 3          # 每隔2秒采样当前情绪
SAMPLES_PER_SUMMARY = 12     # 10次采样后（20秒）输出统计

# AI接口配置
API_KEY = "sk-AAcR9Ipm05waI9qOxFSj0IsErNFLrGcQcLvLKMHHvNYHDHi8"
BASE_URL = "https://api.41box.com/v1/chat/completions"
MODEL = "claude-3-5-sonnet-20240620"
PROMPT = "请用有哲思的或者有趣味的回应来映射以下情绪统计。："
SYSTEM_PROMPT = "你是一个情绪代理AI助手，你的性格在INFP和INFJ之间摇摆，请用15字以内的一个超短句总结你接收到的情绪。"

# 初始化OSC客户端
osc_client = udp_client.SimpleUDPClient("127.0.0.1", 5005)

# 文本AI调用函数（添加系统消息）
def send_ai_query(stat_msg: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"{PROMPT}{stat_msg}"}
        ],
        "max_tokens": 32,
        "temperature": 0.7
    }
    try:
        r = requests.post(BASE_URL, json=payload, headers=headers, timeout=10)
        if r.status_code != 200:
            print(f"AI请求状态码异常: {r.status_code}, 响应: {r.text}")
            return ""
        data = r.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    except Exception as e:
        print("AI请求失败:", e)
        return ""

# 情绪映射
# 将原始表情映射到四大基本类别：活跃(active)、平静(calm)、犹豫(hesitant)、焦躁(anxious)
# 映射关系：
#   neutral(中性) → calm(平静)
#   happy(高兴) → active(活跃)
#   surprise(惊讶) → active(活跃)
#   fear(恐惧) → anxious(焦躁)
#   sad(悲伤) → hesitant(犹豫)
#   angry(愤怒) → anxious(焦躁)
#   disgust(厌恶) → anxious(焦躁)
emotion_to_index = {"neutral":0,"happy":1,"surprise":2,"fear":3,"sad":4,"angry":5,"disgust":6}
emotion_to_category = {"neutral":"calm","happy":"active","surprise":"active","fear":"anxious","sad":"hesitant","angry":"anxious","disgust":"anxious"}
# 类别索引：
#   active:0, calm:1, hesitant:2, anxious:3
category_to_index = {"active":0,"calm":1,"hesitant":2,"anxious":3}

# 计算代理消息发送间隔（秒）
AGENT_MSG_INTERVAL = SAMPLE_INTERVAL * SAMPLES_PER_SUMMARY

# 发送配置信息
osc_client.send_message("/config", ["agent_interval", AGENT_MSG_INTERVAL])

# 基于IoU的目标跟踪器
class IoUTracker:
    def __init__(self, iou_threshold=0.3, max_missed_frames=30):
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed_frames
        self.next_id = 1
        self.tracks = {}
    def update(self, detections):
        results = []
        used_t, used_d = set(), set()
        tids = list(self.tracks)
        if not tids:
            for d in detections:
                tid = self.next_id; self.next_id += 1
                self.tracks[tid] = {"bbox":d, "missed":0}
                results.append((tid, d))
            return results
        m = np.zeros((len(detections), len(tids)))
        for i, d in enumerate(detections):
            for j, tid in enumerate(tids):
                b = self.tracks[tid]["bbox"]
                xa, ya = max(b[0],d[0]), max(b[1],d[1])
                xb, yb = min(b[2],d[2]), min(b[3],d[3])
                wi, hi = max(0,xb-xa), max(0,yb-ya)
                inter = wi*hi
                a1 = (b[2]-b[0])*(b[3]-b[1]); a2 = (d[2]-d[0])*(d[3]-d[1])
                union = a1 + a2 - inter
                m[i,j] = inter/union if union>0 else 0
        pairs = sorted([(m[i,j],i,j) for i in range(m.shape[0]) for j in range(m.shape[1]) if m[i,j]>=self.iou_threshold], key=lambda x:x[0], reverse=True)
        for _,i,j in pairs:
            tid = tids[j]
            if tid in used_t or i in used_d: continue
            used_t.add(tid); used_d.add(i)
            results.append((tid, detections[i]))
        for tid,bb in results:
            self.tracks[tid]["bbox"] = bb; self.tracks[tid]["missed"]=0
        for idx, d in enumerate(detections):
            if idx not in used_d:
                tid = self.next_id; self.next_id+=1
                self.tracks[tid] = {"bbox":d, "missed":0}
                results.append((tid,d))
        for tid in tids:
            if tid not in used_t: self.tracks[tid]["missed"] += 1
        for tid in list(self.tracks):
            if self.tracks[tid]["missed"] > self.max_missed: del self.tracks[tid]
        return results

# 初始化摄像头与模块
cap = cv2.VideoCapture(CAMERA_ID)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, TARGET_W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, TARGET_H)
assert cap.isOpened(), "无法打开摄像头"
logging.info("摄像头初始化完成")
detector = MTCNN()
tracker = IoUTracker(iou_threshold=0.3, max_missed_frames=20)
cv2.namedWindow("Face+Emotion", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Face+Emotion", TARGET_W, TARGET_H)

# 采样统计变量
last_sample = time.time()
sample_count = 0
counts = {'active':0, 'calm':0, 'hesitant':0, 'anxious':0}

# 主循环
while True:
    # 读取帧
    ret, frame = cap.read()
    if not ret:
        logging.error("无法从摄像头获取帧")
        break
    frame = cv2.resize(frame, (TARGET_W, TARGET_H))
    dets = []
    for f in detector.detect_faces(frame):
        x1,y1,w,h = f['box']; x1,y1 = max(0,x1), max(0,y1)
        x2,y2 = x1+w, y1+h
        if x2>x1 and y2>y1: dets.append([x1,y1,x2,y2])
    tracks = tracker.update(dets)
    cats = []
    has_face = False
    for tid, bb in tracks:
        x1,y1,x2,y2 = bb; w,h = x2-x1, y2-y1; cx,cy = x1+w//2, y1+h//2
        face_img = frame[y1:y2, x1:x2]
        try:
            logging.info("开始情绪分析")
            emo = DeepFace.analyze(face_img, actions=['emotion'], enforce_detection=False)[0]['dominant_emotion']
            idx = emotion_to_index.get(emo, -1)
            cat = emotion_to_category.get(emo)
            if cat: cats.append(cat)
            osc_client.send_message("/face", [tid, cx/TARGET_W, cy/TARGET_H, w/TARGET_W, h/TARGET_H, idx])
            has_face = True
            color = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
            cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
            cv2.putText(frame, f"ID:{tid}", (x1,y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.putText(frame, emo, (x1,y2+20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
        except Exception as e:
            print(f"Emotion analyze error for ID {tid}: {e}")
    if not has_face: osc_client.send_message("/no_face", [])
    now = time.time()
    if now-last_sample>=SAMPLE_INTERVAL:
        for c in cats: counts[c]+=1
        sample_count+=1; last_sample=now
        if sample_count>=SAMPLES_PER_SUMMARY:
            vals={'active':counts['active'],'calm':counts['calm'],'hesitant':counts['hesitant'],'anxious':counts['anxious']}
            max_value = max(vals.values())
            max_categories = [cat for cat, count in vals.items() if count == max_value]
            if len(max_categories) > 1:
                total_cat = random.choice(max_categories)
            else:
                total_cat = max_categories[0]
            total_idx = category_to_index[total_cat]
            osc_client.send_message("/agent_emotion", [total_cat, total_idx, counts['active'], counts['calm'], counts['hesitant'], counts['anxious']])
            stat = f"{total_cat},{counts['active']},{counts['calm']},{counts['hesitant']},{counts['anxious']}"
            word = send_ai_query(stat)
            osc_client.send_message("/agent_word", [word])
            print("AI回应:", word)
            counts = {'active':0, 'calm':0, 'hesitant':0, 'anxious':0}; sample_count=0
    cv2.imshow("Face+Emotion", frame)
    if cv2.waitKey(1)&0xFF==ord('q'): break
cap.release(); cv2.destroyAllWindows()
