import base64
import onnxruntime
from pathlib import Path
from . import dddd, ruoyi

BASE_DIR = Path(__file__).resolve().parent
SUPPORTED_BACKENDS = ["dddd", "ruoyi"]

# 验证码识别基类
class BaseCaptchaOcr:
    # Subclass should set a supported backend name.
    backend = ""

    def __init__(self):
        if self.backend not in SUPPORTED_BACKENDS:
            raise ValueError(f"Unsupported backend: {self.backend}")
        self.session = self._init_onnxruntime_session()
        self.charset = self._init_onnxruntime_charset()

    # 初始化神经网络模型
    def _init_onnxruntime_session(self):
        model_path = BASE_DIR / self.backend / "captcha.onnx"
        return onnxruntime.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])

    # 初始化输出字符集
    def _init_onnxruntime_charset(self):
        charset = []
        charset_path = BASE_DIR / self.backend / "charset.txt"
        with open(charset_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                charset.append(line)
        return charset

    # 识别验证码，参数为图像字节
    def identify_image_bytes(self, image: bytes):
        runner = dddd if self.backend == "dddd" else ruoyi
        return runner.run(self.session, self.charset, image)

    # 识别验证码，参数为内联图像，image="data:image/png;base64,iVBO..."
    def identify_image_inline(self, image: str):
        image = image.replace("data:image/png;base64,", "")
        image_bytes = base64.b64decode(image)
        return self.identify_image_bytes(image_bytes)

    # 识别验证码，参数为图像文件路径
    def identify_image_filepath(self, image: str):
        with open(image, "rb") as f:
            filebytes = f.read()
        return self.identify_image_bytes(filebytes)

# 通用验证码识别，识别常规文本
class DdddOcr(BaseCaptchaOcr):
    backend = "dddd"

# 若依验证码识别，专用于识别若依系统的验证码
class RuoyiOcr(BaseCaptchaOcr):
    backend = "ruoyi"
