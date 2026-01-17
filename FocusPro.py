import customtkinter as ctk
import sys
import os
import ctypes
import threading
import time
import json
import random
import subprocess
import urllib.request # 新增：用于网络请求
from datetime import datetime
from PIL import Image, ImageDraw 
import pystray 

# --- 配置与常量 ---
APP_NAME = "FocusPro - 云端搞钱版 V10.0"
CONFIG_FILE = "focus_config.json"
DATA_FILE = "user_data_v10.json" 
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
REDIRECT_IP = "127.0.0.1"
REDIRECT_IPV6 = "::1"

DEFAULT_SITES = [
    "www.bilibili.com", "bilibili.com",
    "www.douyin.com", "douyin.com",
    "www.iqiyi.com", "iqiyi.com",
    "v.qq.com", 
    "www.youtube.com", "youtube.com", "m.youtube.com",
    "googlevideo.com", "ytimg.com",
    "www.instagram.com", "twitter.com", "x.com",
    "weibo.com"
]

DEFAULT_KEYWORDS = ["YouTube", "Bilibili", "哔哩哔哩", "抖音", "Douyin", "爱奇艺", "优酷", "微博"]

# 本地保底文案 (没网的时候用)
BACKUP_QUOTES = [
    "✨ 现在的克制，是为了以后的自由。",
    "💰 搞钱要紧！甲方爸爸在看着你。",
    "🎨 做完这张图，离满级又近了一步。",
    "🚀 专注一小时，胜过摸鱼一整天。",
    "🛑 别看了，那个视频不给金币。"
]

VICTORY_QUOTES = [
    "🎉 干得漂亮！金币+$$，离财富自由又近了一步！",
    "🌟 这种效率，甲方看了都得跪下叫爸爸！",
    "🔥 经验值+$$！你的设计能力正在指数级暴涨！",
    "🚀 还有谁？还有谁能阻挡你搞钱的步伐？",
    "💎 叮！金币到账！给自己买杯咖啡奖励一下？"
]

def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

def flush_dns():
    try: subprocess.run(["ipconfig", "/flushdns"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
    except: pass

def get_active_window_title():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buff = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
    return buff.value

def minimize_window():
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.ShowWindow(hwnd, 6) 

def create_image():
    width = 64; height = 64
    color1 = "#FFD700" 
    color2 = "black"
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 4, width // 4, width * 3 // 4, height * 3 // 4), fill=color2)
    return image

# --- 新增：获取网络鸡汤 ---
def get_online_quote():
    """从一言API获取句子，失败则返回本地备选"""
    try:
        # c=d(文学), c=i(诗词), c=k(哲学)
        url = "https://v1.hitokoto.cn/?c=d&c=i&c=k&encode=json"
        # 设置3秒超时，避免卡顿
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.loads(response.read().decode())
            quote = f"{data['hitokoto']} \n—— {data['from']}"
            return quote
    except Exception as e:
        print(f"网络请求失败: {e}")
        return random.choice(BACKUP_QUOTES)

class FocusApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_NAME)
        self.geometry("650x900") 
        ctk.set_appearance_mode("Dark")
        
        self.config = self.load_config()
        self.user_data = self.load_user_data()
        self.is_running = True 
        self.is_paused = False 
        self.current_task_type = "每日"
        self.seconds_since_break = 0 
        
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.create_widgets()
        
        self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitor_thread.start()
        self.init_tray()
        
        # 启动时异步更新一次鸡汤，防止启动卡顿
        self.update_quote_thread()

    def update_quote_thread(self):
        """后台线程更新鸡汤，不卡界面"""
        def run():
            quote = get_online_quote()
            # 只有当引用标签存在时才更新
            if hasattr(self, 'label_quote'):
                self.label_quote.configure(text=quote)
        threading.Thread(target=run, daemon=True).start()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    if "keywords" not in cfg: cfg["keywords"] = "\n".join(DEFAULT_KEYWORDS)
                    return cfg
            except: pass
        return {"start_hour": "09", "end_hour": "18", "sites": "\n".join(DEFAULT_SITES), "keywords": "\n".join(DEFAULT_KEYWORDS), "clash_mode": True}

    def load_user_data(self):
        default_data = {
            "level": 1, "xp": 0, "max_xp": 100, "gold": 0, 
            "focus_seconds": 0, "tasks": [], "history": [], "last_login_date": ""
        }
        data = default_data
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                    for k, v in default_data.items():
                        if k not in saved_data: saved_data[k] = v
                    data = saved_data
            except: pass
        
        # 每日任务重置
        today_str = datetime.now().strftime("%Y-%m-%d")
        if data["last_login_date"] != today_str:
            for task in data["tasks"]:
                if task.get("type") == "每日": task["completed"] = False
            data["last_login_date"] = today_str
        
        return data

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

    def save_user_data(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.user_data, f, ensure_ascii=False, indent=4)

    def create_widgets(self):
        # Top Quote
        self.frame_top = ctk.CTkFrame(self, corner_radius=15, fg_color="#1e1e1e")
        self.frame_top.pack(pady=15, padx=20, fill="x")
        # 默认先显示本地的，马上会被网络覆盖
        self.label_quote = ctk.CTkLabel(self.frame_top, text="正在连接云端鸡汤库...", 
                                      font=("Microsoft YaHei UI", 14, "bold"), text_color="#FFD700", wraplength=550)
        self.label_quote.pack(pady=15, padx=10)

        # Status
        self.label_status = ctk.CTkLabel(self, text="⚪ 系统就绪", font=("Microsoft YaHei UI", 12), text_color="gray")
        self.label_status.pack(pady=0)

        # Time
        self.frame_time = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_time.pack(pady=5, padx=20, fill="x")
        ctk.CTkLabel(self.frame_time, text="⏰ 锁定时间:").pack(side="left")
        self.entry_start = ctk.CTkEntry(self.frame_time, width=40)
        self.entry_start.insert(0, self.config["start_hour"])
        self.entry_start.pack(side="left", padx=5)
        ctk.CTkLabel(self.frame_time, text="至").pack(side="left")
        self.entry_end = ctk.CTkEntry(self.frame_time, width=40)
        self.entry_end.insert(0, self.config["end_hour"])
        self.entry_end.pack(side="left", padx=5)
        
        # Tabs
        self.tabview = ctk.CTkTabview(self, height=550)
        self.tabview.pack(padx=20, pady=10, fill="both", expand=True)
        
        self.setup_rpg_tab(self.tabview.add("⚔️ 任务面板"))
        self.setup_record_tab(self.tabview.add("🏆 荣誉记录"))
        
        tab_net = self.tabview.add("🌐 网络屏蔽")
        ctk.CTkLabel(tab_net, text="屏蔽网址列表 (一行一个):", anchor="w").pack(fill="x")
        self.textbox_sites = ctk.CTkTextbox(tab_net, height=300)
        self.textbox_sites.pack(pady=5, fill="both", expand=True)
        self.textbox_sites.insert("0.0", self.config["sites"])
        self.switch_clash = ctk.CTkSwitch(tab_net, text="Clash/VPN 兼容模式")
        self.switch_clash.pack(pady=10)
        if self.config["clash_mode"]: self.switch_clash.select()

        tab_win = self.tabview.add("👁️ 窗口屏蔽")
        ctk.CTkLabel(tab_win, text="屏蔽窗口标题关键词:", anchor="w", text_color="#ff5252").pack(fill="x")
        self.textbox_keywords = ctk.CTkTextbox(tab_win, height=300)
        self.textbox_keywords.pack(pady=5, fill="both", expand=True)
        self.textbox_keywords.insert("0.0", self.config["keywords"])

        # Buttons
        self.frame_ctrl = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_ctrl.pack(pady=10, padx=20, fill="x")
        self.frame_ctrl.grid_columnconfigure(0, weight=1)
        self.frame_ctrl.grid_columnconfigure(1, weight=1)

        self.btn_start = ctk.CTkButton(self.frame_ctrl, text="▶ 开启监控", command=self.on_start, fg_color="#00C853", height=40)
        self.btn_start.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.btn_pause = ctk.CTkButton(self.frame_ctrl, text="⏸ 暂停", command=self.on_pause, fg_color="#F9A825", height=40)
        self.btn_pause.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.btn_hide = ctk.CTkButton(self.frame_ctrl, text="🔽 最小化", command=self.hide_window, fg_color="#2196F3", height=30)
        self.btn_hide.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self.btn_quit = ctk.CTkButton(self.frame_ctrl, text="❌ 退出", command=self.quit_app, fg_color="#D32F2F", height=30)
        self.btn_quit.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    def setup_rpg_tab(self, parent):
        frame_stats = ctk.CTkFrame(parent, fg_color="#333333", corner_radius=10)
        frame_stats.pack(pady=5, fill="x")
        self.label_lvl = ctk.CTkLabel(frame_stats, text=f"LV.{self.user_data['level']}", font=("Arial", 24, "bold"), text_color="#4facfe")
        self.label_lvl.pack(side="left", padx=15, pady=10)
        
        frame_xp = ctk.CTkFrame(frame_stats, fg_color="transparent")
        frame_xp.pack(side="left", fill="x", expand=True, padx=5)
        self.label_xp_text = ctk.CTkLabel(frame_xp, text=f"XP: {self.user_data['xp']} / {self.user_data['max_xp']}", font=("Arial", 10))
        self.label_xp_text.pack(anchor="w")
        self.progress_xp = ctk.CTkProgressBar(frame_xp, height=10, progress_color="#4facfe")
        self.progress_xp.pack(fill="x", pady=2)
        self.progress_xp.set(self.user_data['xp'] / self.user_data['max_xp'])
        
        self.label_gold = ctk.CTkLabel(frame_stats, text=f"💰 {int(self.user_data['gold'])}", font=("Arial", 18, "bold"), text_color="#FFD700")
        self.label_gold.pack(side="right", padx=15)

        self.seg_type = ctk.CTkSegmentedButton(parent, values=["每日", "每周", "每月", "长期"], command=self.change_task_type)
        self.seg_type.set("每日")
        self.seg_type.pack(pady=5, fill="x")

        frame_input = ctk.CTkFrame(parent, fg_color="transparent")
        frame_input.pack(pady=5, fill="x")
        self.entry_task = ctk.CTkEntry(frame_input, placeholder_text="输入任务 (每日任务次日重置)...", width=180)
        self.entry_task.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_reward = ctk.CTkEntry(frame_input, placeholder_text="XP", width=50)
        self.entry_reward.pack(side="left", padx=5)
        ctk.CTkButton(frame_input, text="+", width=40, command=self.add_task, fg_color="#00C853").pack(side="left")

        self.scroll_tasks = ctk.CTkScrollableFrame(parent, label_text="任务清单")
        self.scroll_tasks.pack(pady=5, fill="both", expand=True)
        self.refresh_task_list()

    def setup_record_tab(self, parent):
        self.frame_time_stats = ctk.CTkFrame(parent, fg_color="#263238", corner_radius=10)
        self.frame_time_stats.pack(pady=10, fill="x")
        ctk.CTkLabel(self.frame_time_stats, text="🔥 累计专注时长", font=("Arial", 12), text_color="gray").pack(pady=(10,0))
        
        hours = int(self.user_data['focus_seconds'] // 3600)
        mins = int((self.user_data['focus_seconds'] % 3600) // 60)
        self.label_total_time = ctk.CTkLabel(self.frame_time_stats, text=f"{hours} 小时 {mins} 分钟", font=("Arial", 28, "bold"), text_color="#00E676")
        self.label_total_time.pack(pady=(0,10))

        self.scroll_history = ctk.CTkScrollableFrame(parent, label_text="📜 历史记录")
        self.scroll_history.pack(pady=5, fill="both", expand=True)
        self.refresh_history_list()

    def change_task_type(self, value):
        self.current_task_type = value
        self.refresh_task_list()

    def refresh_task_list(self):
        for widget in self.scroll_tasks.winfo_children(): widget.destroy()
        for index, task in enumerate(self.user_data['tasks']):
            if task.get('type', '每日') != self.current_task_type: continue
            
            is_done = task.get('completed', False)
            bg_color = "#1B5E20" if is_done else "#424242"
            f = ctk.CTkFrame(self.scroll_tasks, fg_color=bg_color, cursor="hand2")
            f.pack(pady=2, fill="x")
            f.bind("<Button-1>", lambda e, idx=index: self.toggle_task(idx))
            
            chk = "☑" if is_done else "☐"
            l1 = ctk.CTkLabel(f, text=chk, font=("Arial", 18), text_color="white")
            l1.pack(side="left", padx=10, pady=8)
            l1.bind("<Button-1>", lambda e, idx=index: self.toggle_task(idx))
            
            name = f"~~{task['name']}~~" if is_done else task['name']
            l2 = ctk.CTkLabel(f, text=name, font=("Arial", 14))
            l2.pack(side="left", padx=5)
            l2.bind("<Button-1>", lambda e, idx=index: self.toggle_task(idx))
            
            l3 = ctk.CTkLabel(f, text=f"+{task['xp']}XP", text_color="#4facfe", font=("Arial", 10))
            l3.pack(side="right", padx=10)
            l3.bind("<Button-1>", lambda e, idx=index: self.toggle_task(idx))

            ctk.CTkButton(f, text="🗑", width=30, height=20, fg_color="#D32F2F", command=lambda idx=index: self.delete_task(idx)).pack(side="right", padx=5)

    def add_task(self):
        name = self.entry_task.get().strip()
        try: xp = int(self.entry_reward.get().strip())
        except: xp = 50
        if not name: return
        self.user_data['tasks'].append({"name": name, "xp": xp, "type": self.current_task_type, "completed": False})
        self.entry_task.delete(0, "end")
        self.save_user_data()
        self.refresh_task_list()

    def delete_task(self, index):
        del self.user_data['tasks'][index]
        self.save_user_data()
        self.refresh_task_list()

    def toggle_task(self, index):
        task = self.user_data['tasks'][index]
        val = task['xp']; gold = int(val / 5)
        if not task['completed']:
            task['completed'] = True
            self.user_data['xp'] += val
            self.user_data['gold'] += gold
            self.user_data['history'].insert(0, f"[{datetime.now().strftime('%m-%d %H:%M')}] 完成: {task['name']} (+{val}XP)")
            # 胜利时依然使用金币/RPG相关的本地文案，更有成就感
            self.label_quote.configure(text=random.choice(VICTORY_QUOTES).replace("$$", str(val)), text_color="#00E676")
            if self.user_data['xp'] >= self.user_data['max_xp']:
                self.user_data['level'] += 1
                self.user_data['xp'] -= self.user_data['max_xp']
                self.user_data['max_xp'] = int(self.user_data['max_xp'] * 1.5)
                self.label_status.configure(text=f"🎉 升级！LV.{self.user_data['level']}", text_color="#FFD700")
        else:
            task['completed'] = False
            self.user_data['xp'] -= val
            self.user_data['gold'] -= gold
            if self.user_data['xp'] < 0: self.user_data['xp'] = 0
            self.label_quote.configure(text="😅 撤销奖励...", text_color="orange")
        self.save_user_data()
        self.update_stats_ui()
        self.refresh_task_list()
        self.refresh_history_list()

    def refresh_history_list(self):
        for w in self.scroll_history.winfo_children(): w.destroy()
        for item in self.user_data['history'][:50]:
            ctk.CTkLabel(self.scroll_history, text=item, anchor="w", font=("Arial", 12), text_color="#B0BEC5").pack(fill="x", padx=10, pady=2)

    def update_stats_ui(self):
        self.label_lvl.configure(text=f"LV.{self.user_data['level']}")
        self.label_gold.configure(text=f"💰 {int(self.user_data['gold'])}")
        self.label_xp_text.configure(text=f"XP: {int(self.user_data['xp'])} / {self.user_data['max_xp']}")
        self.progress_xp.set(self.user_data['xp'] / self.user_data['max_xp'])
        h = int(self.user_data['focus_seconds'] // 3600)
        m = int((self.user_data['focus_seconds'] % 3600) // 60)
        if hasattr(self, 'label_total_time'): self.label_total_time.configure(text=f"{h} 小时 {m} 分钟")

    def show_rest_popup(self):
        top = ctk.CTkToplevel(self)
        top.title("🛑 休息一下！")
        top.geometry("400x250")
        top.attributes("-topmost", True) 
        
        ctk.CTkLabel(top, text="⚠️ 连续搞钱1小时啦", font=("Arial", 18, "bold"), text_color="#ff5252").pack(pady=20)
        
        # 弹窗时也尝试获取一条网络鸡汤
        quote = get_online_quote()
        ctk.CTkLabel(top, text=quote, font=("Arial", 14), wraplength=350).pack(pady=10, padx=20)
        
        ctk.CTkLabel(top, text="建议：离开屏幕，休息 20 分钟", font=("Arial", 12), text_color="gray").pack(pady=10)
        ctk.CTkButton(top, text="好的，我去休息", command=top.destroy, fg_color="#00C853").pack(pady=20)

    def on_start(self):
        self.save_config()
        self.is_paused = False
        self.label_status.configure(text="🔥 监控中...", text_color="#00C853")
        # 每次开始监控，也刷新一下顶部的鸡汤
        self.update_quote_thread()

    def on_pause(self):
        self.is_paused = True
        self.unblock_action()
        self.label_status.configure(text="⏸ 已暂停", text_color="orange")

    def monitoring_loop(self):
        last_time = time.time()
        while self.is_running:
            try:
                current_time = time.time()
                time_diff = current_time - last_time
                last_time = current_time
                
                now = datetime.now()
                start = int(self.entry_start.get())
                end = int(self.entry_end.get())
                is_work_time = (start <= now.hour < end) if start < end else (start <= now.hour or now.hour < end)

                if not self.is_paused and is_work_time:
                    self.user_data['focus_seconds'] += time_diff
                    self.seconds_since_break += time_diff 
                    
                    if self.seconds_since_break >= 3600:
                        self.seconds_since_break = 0 
                        self.after(0, self.show_rest_popup)
                    
                    if int(self.user_data['focus_seconds']) % 60 == 0:
                        self.save_user_data()
                        self.after(0, self.update_stats_ui)
                    
                    self.block_action_network()
                    self.block_action_window()
                else:
                    self.unblock_action()
                
                time.sleep(1)
            except: time.sleep(5)

    def block_action_network(self):
        sites = [line.strip() for line in self.textbox_sites.get("0.0", "end").strip().split('\n') if line.strip()]
        try:
            with open(HOSTS_PATH, 'r+') as f:
                content = f.read(); f.seek(0, 2)
                for site in sites:
                    if site not in content:
                        f.write(f"\n{REDIRECT_IP} {site}\n{REDIRECT_IP} www.{site}")
                        f.write(f"\n{REDIRECT_IPV6} {site}\n{REDIRECT_IPV6} www.{site}")
            if self.switch_clash.get(): flush_dns()
        except: pass

    def block_action_window(self):
        keywords = [line.strip() for line in self.textbox_keywords.get("0.0", "end").strip().split('\n') if line.strip()]
        title = get_active_window_title()
        for kw in keywords:
            if kw.lower() in title.lower(): minimize_window(); break

    def unblock_action(self):
        sites = [line.strip() for line in self.textbox_sites.get("0.0", "end").strip().split('\n') if line.strip()]
        try:
            with open(HOSTS_PATH, 'r') as f: lines = f.readlines()
            with open(HOSTS_PATH, 'w') as f:
                for line in lines:
                    if not any(site in line for site in sites): f.write(line)
            if self.switch_clash.get(): flush_dns()
        except: pass

    def init_tray(self):
        menu = pystray.Menu(pystray.MenuItem("显示面板", self.show_window, default=True), pystray.MenuItem("退出", self.quit_app))
        self.icon = pystray.Icon("FocusPro", create_image(), "RPG专注模式", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()
    def hide_window(self): self.withdraw() 
    def show_window(self, icon=None, item=None): self.deiconify(); self.lift(); self.focus_force()
    def quit_app(self, icon=None, item=None): 
        self.is_running = False; self.unblock_action(); self.save_user_data()
        if self.icon: self.icon.stop()
        self.destroy(); sys.exit()

if __name__ == "__main__":
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    else:
        app = FocusApp()
        app.mainloop()