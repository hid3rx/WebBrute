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

    # 统一成 BGR 三通道
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    # 按模型要求处理到 3x32x640：等比缩放 + 右侧补零
    target_height = 32
    target_width = 640
    h, w = image.shape[:2]
    scale = min(target_width / w, target_height / h)
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    padded = np.zeros((target_height, target_width, 3), dtype=np.uint8)
    padded[:new_h, :new_w, :] = resized

    image_array = padded.astype(np.float32) / 255.0
    image_array = np.transpose(image_array, (2, 0, 1))  # HWC -> CHW
    image_array = np.expand_dims(image_array, axis=0)   # (1, 3, 32, 640)

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
