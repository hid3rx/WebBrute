import cv2
import numpy as np
import onnxruntime

onnxruntime.set_default_logger_severity(3)

def run(session: onnxruntime.InferenceSession, charset: list[str], img: bytes) -> str:

    ##############
    # 处理图片格式
    ##############

    arr = np.frombuffer(img, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)

    # RGBA：把 alpha 通道合并到白色背景
    if image.ndim == 3 and image.shape[2] == 4:
        alpha = image[:, :, 3:4].astype(np.float32) / 255.0
        rgb = image[:, :, :3].astype(np.float32)
        image = (rgb * alpha + 255.0 * (1.0 - alpha)).astype(np.uint8)

    # 转灰度
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 等比缩放到高度 64
    h, w = image.shape
    target_height = 64
    target_width = max(1, int(w * target_height / h))
    image = cv2.resize(image, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)

    image_array = image.astype(np.float32) / 255.0
    image_array = image_array[np.newaxis, np.newaxis, :]  # (1, 1, H, W)

    ##############
    # 验证码识别
    ##############

    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: image_array})[0]

    if output.ndim == 3:
        if output.shape[1] == 1:
            indices = np.argmax(output[:, 0, :], axis=1)
        else:
            indices = np.argmax(output[0, :, :], axis=1)
    else:
        indices = np.argmax(output, axis=-1)
        if np.isscalar(indices):
            indices = np.array([indices])
    
    chars = []
    previous = None
    for index in indices:
        current = int(index)
        if current != previous and current != 0 and 0 <= current < len(charset):
            chars.append(charset[current])
        previous = current

    return "".join(chars)
