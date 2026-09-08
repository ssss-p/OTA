import json
import os


def load_json_files(json_dir):
    """读取目录下所有 json 文件，返回 {文件名（不含扩展名）: 数据} 的字典。"""
    data = {}
    for filename in os.listdir(json_dir):
        if filename.endswith(".json"):
            name = os.path.splitext(filename)[0]
            filepath = os.path.join(json_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data[name] = json.load(f)
    return data


def load_json_file(filepath):
    """读取单个 json 文件。"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)
