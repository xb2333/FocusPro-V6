import customtkinter as ctk
import sys
import os
import ctypes
import threading
import time
import json
import random
import subprocess
from datetime import datetime
from PIL import Image, ImageDraw 
import pystray 

# --- 配置与常量 ---
APP_NAME = "FocusPro - 终极搞钱版 V6.0"
CONFIG_FILE = "focus_config.json"
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
REDIRECT_IP = "127.0.0.1"
REDIRECT_IPV6 = "::1"

# 1. 网络层屏蔽列表 (虽然Clash会绕过，但为了双重保险依然保留)
DEFAULT_SITES = [
    "www.bilibili.com", "bilibili.com",
    "www.douyin.com", "douyin.com",
    "www.iqiyi.com", "iqiyi.com",
    "v.qq.com", 
    "www.youtube.com", "youtube.com", "m.youtube.com",
    "googlevideo.com", "ytimg.com", # YouTube视频流域名
    "www.instagram.com", "twitter.com", "x.com",
    "weibo.com"
]

# 2. 【新增】窗口猎杀关键词 (无视代理，只要标题有这些字就干掉)
DEFAULT_KEYWORDS = [
    "YouTube", "Bilibili", "哔哩哔哩", 
    "抖音", "Douyin", 
    "爱奇艺", "iQIYI", 
    "腾讯视频", "优酷", "Youku",
    "微博", "Weibo"
]

QUOTES = [
    "✨ 既然选择了自由职业，就要配得上这份自由。",
    "💰 现在的每一分钟专注，都是未来的存款。",
    "🎨 别改图了？那把尾款结一下？",
    "🚀 刷视频很爽，但交不出稿真的很狼狈。",
    "🛑 此时此刻，你的竞争对手正在干活。",
    "🌟 只有极致的自律，才能带来极致的自由。",
    "💪 再坚持一下，今天的单子做完了吗？"
]

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def flush_dns():
    try:
        subprocess.run(["ipconfig", "/flushdns"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    except:
        pass

# --- 窗口操作核心函数 ---
def get_active_window_title():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value

def minimize_window():
    """强制最小化当前窗口"""
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.ShowWindow(hwnd, 6) # 6 = SW_MINIMIZE

# --- 托盘图标 ---
def create_image():
    width = 64
    height = 64
    color1 = "#D32F2F" # 换个警示红
    color2 = "white"
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 4, width // 4, width * 3 // 4, height * 3 // 4), fill=color2)
    return image

class FocusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("550x850") 
        ctk.set_appearance_mode("Dark")
        
        self.config = self.load_config()
        self.is_running = True 
        self.is_paused = False 
        
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        self.create_widgets()
        
        # 启动双重监控线程
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()

        self.init_tray()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    # 兼容旧配置，如果没有keywords字段则添加
                    if "keywords" not in cfg:
                        cfg["keywords"] = "\n".join(DEFAULT_KEYWORDS)
                    return cfg
            except:
                pass
        return {
            "start_hour": "09", 
            "end_hour": "18", 
            "sites": "\n".join(DEFAULT_SITES), 
            "keywords": "\n".join(DEFAULT_KEYWORDS),
            "clash_mode": True
        }

    def save_config(self):
        config = {
            "start_hour": self.entry_start.get(),
            "end_hour": self.entry_end.get(),
            "sites": self.textbox_sites.get("0.0", "end").strip(),
            "keywords": self.textbox_keywords.get("0.0", "end").strip(),
            "clash_mode": self.switch_clash.get()
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    def create_widgets(self):
        # 顶部
        self.frame_top = ctk.CTkFrame(self, corner_radius=15, fg_color="#1e1e1e")
        self.frame_top.pack(pady=20, padx=20, fill="x")
        self.label_quote = ctk.CTkLabel(self.frame_top, text=random.choice(QUOTES), 
                                      font=("Microsoft YaHei UI", 16, "bold"), text_color="#4facfe", wraplength=400)
        self.label_quote.pack(pady=20, padx=10)

        self.label_status = ctk.CTkLabel(self, text="⚪ 初始化中...", font=("Microsoft YaHei UI", 14, "bold"), text_color="gray")
        self.label_status.pack(pady=5)

        # 时间
        self.frame_time = ctk.CTkFrame(self)
        self.frame_time.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(self.frame_time, text="⏰ 锁定时间:").pack(side="left", padx=10, pady=10)
        self.entry_start = ctk.CTkEntry(self.frame_time, width=50)
        self.entry_start.insert(0, self.config["start_hour"])
        self.entry_start.pack(side="left", padx=5)
        ctk.CTkLabel(self.frame_time, text="至").pack(side="left")
        self.entry_end = ctk.CTkEntry(self.frame_time, width=50)
        self.entry_end.insert(0, self.config["end_hour"])
        self.entry_end.pack(side="left", padx=5)
        ctk.CTkLabel(self.frame_time, text="点").pack(side="left")

        # Tab视图：分网络屏蔽和窗口屏蔽
        self.tabview = ctk.CTkTabview(self, height=350)
        self.tabview.pack(padx=20, pady=10, fill="x")
        
        tab_net = self.tabview.add("🌐 网络/域名屏蔽")
        tab_win = self.tabview.add("👁️ 窗口/标题屏蔽")

        # Tab 1: 网络屏蔽
        ctk.CTkLabel(tab_net, text="一行一个网址 (Clash用户请看Tab 2):", anchor="w").pack(fill="x")
        self.textbox_sites = ctk.CTkTextbox(tab_net, height=250)
        self.textbox_sites.pack(pady=5, fill="both", expand=True)
        self.textbox_sites.insert("0.0", self.config["sites"])

        # Tab 2: 窗口屏蔽 (新功能)
        ctk.CTkLabel(tab_win, text="当窗口标题包含这些词时，强制最小化:", anchor="w", text_color="#ff5252").pack(fill="x")
        self.textbox_keywords = ctk.CTkTextbox(tab_win, height=250)
        self.textbox_keywords.pack(pady=5, fill="both", expand=True)
        if "keywords" in self.config:
            self.textbox_keywords.insert("0.0", self.config["keywords"])
        else:
            self.textbox_keywords.insert("0.0", "\n".join(DEFAULT_KEYWORDS))

        # Clash 开关
        self.switch_clash = ctk.CTkSwitch(self, text="Clash/VPN 兼容模式")
        self.switch_clash.pack(pady=5)
        if self.config["clash_mode"]: self.switch_clash.select()

        # 按钮区
        self.frame_ctrl = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_ctrl.pack(pady=10, padx=20, fill="x")
        self.frame_ctrl.grid_columnconfigure(0, weight=1)
        self.frame_ctrl.grid_columnconfigure(1, weight=1)

        self.btn_start = ctk.CTkButton(self.frame_ctrl, text="▶ 开启监控", command=self.on_start, 
                                     fg_color="#00C853", hover_color="#009624", height=50, font=("Arial", 14, "bold"))
        self.btn_start.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.btn_pause = ctk.CTkButton(self.frame_ctrl, text="⏸ 暂停", command=self.on_pause, 
                                     fg_color="#F9A825", hover_color="#F57F17", height=50, font=("Arial", 14, "bold"))
        self.btn_pause.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.btn_hide = ctk.CTkButton(self.frame_ctrl, text="🔽 最小化", command=self.hide_window, 
                                     fg_color="#2196F3")
        self.btn_hide.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.btn_quit = ctk.CTkButton(self.frame_ctrl, text="❌ 退出", command=self.quit_app, 
                                     fg_color="#D32F2F")
        self.btn_quit.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    def get_list(self, textbox):
        content = textbox.get("0.0", "end").strip()
        return [line.strip() for line in content.split('\n') if line.strip()]

    def on_start(self):
        self.save_config()
        self.is_paused = False
        self.label_status.configure(text="✅ 监控全开 (网络+窗口检测)", text_color="#00C853")

    def on_pause(self):
        self.is_paused = True
        self.unblock_action()
        self.label_status.configure(text="⏸ 已暂停", text_color="orange")

    # --- 监控逻辑 ---
    def block_action_network(self):
        sites = self.get_list(self.textbox_sites)
        try:
            with open(HOSTS_PATH, 'r+') as f:
                content = f.read()
                f.seek(0, 2)
                for site in sites:
                    if site not in content:
                        f.write(f"\n{REDIRECT_IP} {site}")
                        f.write(f"\n{REDIRECT_IP} www.{site}" if "www" not in site else "")
                        f.write(f"\n{REDIRECT_IPV6} {site}") 
                        f.write(f"\n{REDIRECT_IPV6} www.{site}" if "www" not in site else "")
            if self.switch_clash.get(): flush_dns()
        except Exception: pass

    def block_action_window(self):
        """检测窗口标题，违规直接最小化"""
        keywords = self.get_list(self.textbox_keywords)
        current_title = get_active_window_title()
        
        # 遍历关键词
        for kw in keywords:
            if kw.lower() in current_title.lower():
                # 发现违规窗口
                print(f"Detected blocked window: {current_title}")
                minimize_window() 
                # 这里可以加个弹窗警告，但为了不打断思路，只做最小化处理
                break

    def unblock_action(self):
        sites = self.get_list(self.textbox_sites)
        try:
            with open(HOSTS_PATH, 'r') as f: lines = f.readlines()
            with open(HOSTS_PATH, 'w') as f:
                for line in lines:
                    if not any(site in line for site in sites): f.write(line)
            if self.switch_clash.get(): flush_dns()
        except: pass

    def monitoring_loop(self):
        while self.is_running:
            try:
                if self.is_paused:
                    time.sleep(2)
                    continue

                now = datetime.now()
                start = int(self.entry_start.get())
                end = int(self.entry_end.get())
                
                if start < end:
                    is_work_time = start <= now.hour < end
                else:
                    is_work_time = start <= now.hour or now.hour < end
                
                if is_work_time:
                    self.label_status.configure(text=f"🔥 搞钱中 ({start}-{end})", text_color="#ff5252")
                    # 1. 执行网络屏蔽
                    self.block_action_network()
                    # 2. 执行窗口猎杀 (高频检测：每1秒查一次)
                    self.block_action_window()
                    time.sleep(1) 
                else:
                    self.label_status.configure(text="☕ 休息时间", text_color="#4facfe")
                    self.unblock_action()
                    time.sleep(5)
            except:
                time.sleep(5)

    def init_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("显示面板", self.show_window, default=True),
            pystray.MenuItem("彻底退出", self.quit_app)
        )
        self.icon = pystray.Icon("FocusPro", create_image(), "搞钱专注模式", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def hide_window(self):
        self.withdraw() 
    
    def show_window(self, icon=None, item=None):
        self.deiconify() 
        self.lift()
        self.focus_force()

    def quit_app(self, icon=None, item=None):
        self.is_running = False
        self.unblock_action() 
        if self.icon: self.icon.stop() 
        self.destroy() 
        sys.exit()

if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    else:
        app = FocusApp()
        app.mainloop()