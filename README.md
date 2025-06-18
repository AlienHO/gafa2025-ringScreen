# GAFA2025 RingScreen 项目

## 项目概述
实时人群情绪分析系统，通过摄像头捕捉人脸表情，分析群体情绪状态，并通过OSC协议发送数据到TouchDesigner进行可视化。

## 功能模块
1. **主程序**：`emotion_detect_normalize_ai_ver2.py`
   - 实时人脸检测与情绪分析
   - 情绪数据聚合与分类
   - OSC消息发送
2. **测试程序**：`test_osc_sender_v2.py`
   - 模拟主程序行为
   - 随机生成测试数据
3. **依赖文件**：`requirements.txt`

## 快速开始

### 环境配置
```bash
# 创建虚拟环境
python -m venv .venv

# 激活环境 (Mac/Linux)
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 运行主程序
```bash
python emotion_detect_normalize_ai_ver2.py
```

### 运行测试程序
```bash
python test_osc_sender_v2.py
```

## 配置参数
| 文件 | 参数 | 说明 |
|------|------|------|
| `emotion_detect...` | `SAMPLE_INTERVAL` | 采样间隔(秒) |
| | `SAMPLES_PER_SUMMARY` | 汇总采样次数 |
| `test_osc...` | `AGENT_MSG_INTERVAL` | 测试消息间隔(秒) |

## OSC消息协议

### `/face` 消息
- **功能**：传输单个人脸数据
- **参数**：
  1. `ID` (int): 人脸跟踪ID
  2. `x` (float): 人脸中心点X坐标 (0.0~1.0)
  3. `y` (float): 人脸中心点Y坐标 (0.0~1.0)
  4. `w` (float): 人脸宽度 (0.0~1.0)
  5. `h` (float): 人脸高度 (0.0~1.0)
  6. `emo_idx` (int): 情绪索引 (0-6对应7种基础情绪)

### `/agent_emotion` 消息
- **功能**：传输聚合情绪数据
- **参数**：
  1. `dominant` (string): 主导情绪类别名称
  2. `idx` (int): 主导情绪索引 (0-3对应4种类别)
  3. `a_count` (int): active(活跃)类别计数
  4. `c_count` (int): calm(平静)类别计数
  5. `h_count` (int): hesitant(犹豫)类别计数
  6. `anx_count` (int): anxious(焦躁)类别计数

### `/agent_word` 消息
- **功能**：传输情绪描述词
- **参数**：
  1. `word` (string): 描述群体情绪的中文词语

### `/config` 消息
- **功能**：传输配置信息
- **参数**：
  1. `config_name` (string): 配置项名称 ("agent_interval")
  2. `value` (float): 配置值 (单位：秒)

## 注意事项
1. 首次运行会自动下载情绪模型
2. 需要配置OpenAI API密钥用于情绪描述词生成