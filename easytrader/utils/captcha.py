import re
import requests
from PIL import Image, ImageEnhance
import numpy as np
from collections import Counter
import pytesseract


def captcha_recognize(img_path):
    """优化后的验证码识别函数，针对4位数字验证码"""
    im = Image.open(img_path).convert("L")  # 灰度化
    # 增强对比度
    enhancer = ImageEnhance.Contrast(im)
    im = enhancer.enhance(1.5)  # 对比度增强1.5倍
    # 多重识别与投票
    results = []
    for threshold in [180, 200, 220]:  # 测试不同阈值
        table = [0 if i < threshold else 1 for i in range(256)]
        out = im.point(table, "1")  # 二值化
        num = pytesseract.image_to_string(out, config='--psm 8 -c tessedit_char_whitelist=0123456789').strip()
        num = ''.join(filter(str.isdigit, num))  # 仅保留数字
        if len(num) == 4:  # 确保结果为4位
            results.append(num)
    if results:
        return Counter(results).most_common(1)[0][0]  # 选择出现次数最多的结果
    # 若自动识别失败，调用手动输入
    return input_verify_code_manual(img_path)


def recognize_verify_code(image_path, broker="ht"):
    """识别验证码，返回识别后的字符串，使用优化后的 tesseract 或云端服务
    :param image_path: 图片路径
    :param broker: 券商 ['ht', 'yjb', 'gf', 'yh']
    :return recognized: verify code string"""
    if broker == "gf":
        return detect_gf_result(image_path)
    if broker in ["yh_client", "gj_client"]:
        return detect_yh_client_result(image_path)
    # 优先尝试云端服务
    try:
        return detect_yh_client_result(image_path)  # 假设ht也使用云端服务
    except (exceptions.TradeError, requests.RequestException):
        # 失败后使用本地Tesseract
        return captcha_recognize(image_path)


def detect_yh_client_result(image_path):
    """封装了Tesseract的识别，部署在阿里云上，
    服务端源码地址为： https://github.com/shidenggui/yh_verify_code_docker"""
    api = "http://yh.ez.shidenggui.com:5000/yh_client"
    with open(image_path, "rb") as f:
        rep = requests.post(api, files={"image": f})
    if rep.status_code != 201:
        error = rep.json()["message"]
        raise exceptions.TradeError("request {} error: {}".format(api, error))
    result = rep.json()["result"]
    return ''.join(filter(str.isdigit, result))  # 确保仅返回数字


def input_verify_code_manual(image_path):
    from PIL import Image
    image = Image.open(image_path)
    image.show()
    code = input("image path: {}, input verify code answer (4 digits): ".format(image_path))
    if not (code.isdigit() and len(code) == 4):
        raise ValueError("Please input exactly 4 digits")
    return code


def default_verify_code_detect(image_path):
    from PIL import Image
    img = Image.open(image_path)
    return invoke_tesseract_to_recognize(img)


def detect_gf_result(image_path):
    from PIL import ImageFilter, Image
    img = Image.open(image_path)
    if hasattr(img, "width"):
        width, height = img.width, img.height
    else:
        width, height = img.size
    for x in range(width):
        for y in range(height):
            if img.getpixel((x, y)) < (100, 100, 100):
                img.putpixel((x, y), (256, 256, 256))
    gray = img.convert("L")
    two = gray.point(lambda p: 0 if 68 < p < 90 else 256)
    min_res = two.filter(ImageFilter.MinFilter)
    med_res = min_res.filter(ImageFilter.MedianFilter)
    for _ in range(2):
        med_res = med_res.filter(ImageFilter.MedianFilter)
    return invoke_tesseract_to_recognize(med_res)


def invoke_tesseract_to_recognize(img):
    try:
        res = pytesseract.image_to_string(img, config='--psm 8 -c tessedit_char_whitelist=0123456789')
    except FileNotFoundError:
        raise Exception(
            "tesseract 未安装，请至 https://github.com/tesseract-ocr/tesseract/wiki 查看安装教程"
        )
    valid_chars = ''.join(filter(str.isdigit, res))
    return valid_chars
