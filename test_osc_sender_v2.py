import random
import time
from pythonosc import udp_client
import threading

# OSC Configuration
OSC_IP = "127.0.0.1"
OSC_PORT = 5005
osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# Emotion Configuration
EMOTION_CATEGORIES = ['active', 'calm', 'hesitant', 'anxious']
CATEGORY_TO_INDEX = {cat: idx for idx, cat in enumerate(EMOTION_CATEGORIES)}

# Global emotion counters
emotion_counts = {cat: 0 for cat in EMOTION_CATEGORIES}

# Word generation pool
DESCRIPTIVE_WORDS = [
    "充满活力的", "平静祥和的", "犹豫不前的", "焦躁不安的",
    "热情洋溢的", "冷静自若的", "举棋不定的", "心烦意乱的"
]

# 配置参数
AGENT_MSG_INTERVAL = 5.0  # 测试程序固定5秒间隔

# 发送配置信息
osc_client.send_message("/config", ["agent_interval", AGENT_MSG_INTERVAL])

def simulate_face_detection():
    """Simulate face detection data at random intervals"""
    tid = random.randint(1, 10)  # Tracking ID
    # Normalized coordinates (0-1)
    cx, cy = random.random(), random.random()
    w, h = random.uniform(0.1, 0.4), random.uniform(0.1, 0.4)
    # Random emotion index (0-6)
    emotion_idx = random.randint(0, 6)
    
    osc_client.send_message("/face", [tid, cx, cy, w, h, emotion_idx])
    print(f"Sent /face: [ID={tid}, x={cx:.2f}, y={cy:.2f}, w={w:.2f}, h={h:.2f}, emo={emotion_idx}]")


def update_emotion_counts():
    """Update emotion counts with random data"""
    global emotion_counts
    # Simulate 1-5 faces detected in this interval
    for _ in range(random.randint(1, 5)):
        # Random emotion category
        category = random.choice(EMOTION_CATEGORIES)
        emotion_counts[category] += 1


def generate_descriptive_word(counts_dict):
    """Generate a descriptive word based on emotion counts"""
    # Simple implementation: choose random word
    return random.choice(DESCRIPTIVE_WORDS)


def send_agent_messages():
    """Send both agent_emotion and agent_word messages"""
    global emotion_counts
    # 1. Prepare agent_emotion data
    max_count = max(emotion_counts.values())
    dominant_cats = [cat for cat, count in emotion_counts.items() if count == max_count]
    dominant_cat = random.choice(dominant_cats) if len(dominant_cats) > 1 else dominant_cats[0]
    dominant_idx = CATEGORY_TO_INDEX[dominant_cat]
    
    # Build message: [dominant_cat, dominant_idx, active, calm, hesitant, anxious]
    message_data = [
        dominant_cat,
        dominant_idx,
        emotion_counts['active'],
        emotion_counts['calm'],
        emotion_counts['hesitant'],
        emotion_counts['anxious']
    ]
    osc_client.send_message("/agent_emotion", message_data)
    
    # 2. Prepare agent_word data
    word = generate_descriptive_word(emotion_counts)
    osc_client.send_message("/agent_word", [word])
    
    print(f"Sent /agent_emotion: {message_data}")
    print(f"Sent /agent_word: '{word}'")
    
    # Reset counts
    emotion_counts = {cat: 0 for cat in EMOTION_CATEGORIES}


def main_loop():
    """Main simulation loop for face detection"""
    simulate_face_detection()
    update_emotion_counts()
    threading.Timer(0.1, main_loop).start()  # ~10Hz


def agent_message_scheduler():
    """Schedule agent message sending every 5 seconds"""
    send_agent_messages()
    threading.Timer(AGENT_MSG_INTERVAL, agent_message_scheduler).start()


if __name__ == "__main__":
    print("Starting enhanced OSC test sender (v2)...")
    main_loop()               # Start face/emotion simulation
    agent_message_scheduler()  # Start agent message scheduler
    
    # Keep program running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Test sender stopped")
