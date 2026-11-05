"""Independent, read-only phone screen rotation demonstration."""
import math
import queue
import time
import tkinter as tk
from tkinter import ttk, messagebox
from serial.tools import list_ports
from .worker import Worker
from .screen_orientation import Orientation, quaternion_up, acceleration_up, simulated_up, angle


class PhoneDemo(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('WHEELTEC IMU · 手机自动转屏 Demo')
        self.geometry('1050x720')
        self.minsize(900, 650)
        self.events = queue.Queue(); self.worker = None; self.closing = False
        self.detector = Orientation(); self.up = None; self.last_good = 0; self.good = 0
        self.mode = tk.StringVar(value='真实串口'); self.source = tk.StringVar(value='姿态四元数')
        self.port = tk.StringVar(); self.status = tk.StringVar(value='未连接 · 无实时数据')
        self.details = tk.StringVar(value='等待有效姿态数据')
        self.rotation = tk.DoubleVar(value=0); self.tilt = tk.DoubleVar(value=90)
        bar = ttk.Frame(self, padding=8); bar.pack(fill='x')
        ttk.Label(bar, text='模式').pack(side='left')
        self.modebox = ttk.Combobox(bar, textvariable=self.mode, values=['真实串口','模拟模式'], state='readonly', width=10)
        self.modebox.pack(side='left', padx=5); self.modebox.bind('<<ComboboxSelected>>', self.change_mode)
        ttk.Label(bar, text='串口').pack(side='left')
        self.ports = ttk.Combobox(bar, textvariable=self.port, width=10); self.ports.pack(side='left', padx=4)
        ttk.Button(bar, text='扫描', command=self.scan).pack(side='left')
        self.connect = ttk.Button(bar, text='连接', command=self.toggle); self.connect.pack(side='left', padx=6)
        ttk.Label(bar, text='921600 · 只读    数据源').pack(side='left')
        self.sourcebox = ttk.Combobox(bar, textvariable=self.source, state='readonly', width=20,
            values=['姿态四元数','重力加速度（-a）'])
        self.sourcebox.pack(side='left', padx=5); self.sourcebox.bind('<<ComboboxSelected>>', self.change_source)
        ttk.Label(self, textvariable=self.status, padding=(10,3)).pack(anchor='w')
        main = ttk.Frame(self, padding=8); main.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(main, bg='#101b2d', highlightthickness=0, width=530, height=570)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.canvas.bind('<Configure>', lambda e: self.draw())
        panel = ttk.Frame(main, padding=(18,0)); panel.pack(side='left', fill='y')
        ttk.Label(panel, text='方向判定', font=('Microsoft YaHei', 15, 'bold')).pack(anchor='w', pady=(0,10))
        ttk.Label(panel, textvariable=self.details, justify='left', font=('Microsoft YaHei', 10)).pack(anchor='w')
        ttk.Separator(panel).pack(fill='x', pady=12)
        ttk.Label(panel, text='机身固定：顶 +X  |  右 +Y\n屏幕朝前 −Z（面向用户）\n蓝箭头：世界上在机身平面的投影\n红箭头：世界下 / 重力投影', justify='left').pack(anchor='w')
        ttk.Label(panel, text='四态：物理顺时针角 → 内容朝向\n0° 正竖屏 → +X 顶\n90° 右转横屏 → −Y 左边\n180° 倒竖屏 → −X 底\n270° 左转横屏 → +Y 右边', justify='left').pack(anchor='w', pady=12)
        self.simframe = ttk.LabelFrame(panel, text='模拟控制（不占串口）', padding=8); self.simframe.pack(fill='x')
        ttk.Label(self.simframe, text='手机物理顺时针角').pack(anchor='w')
        tk.Scale(self.simframe, from_=0, to=359, orient='horizontal', variable=self.rotation, length=260).pack(fill='x')
        buttons = ttk.Frame(self.simframe); buttons.pack(fill='x')
        for v in (0,90,180,270):
            ttk.Button(buttons, text=str(v)+'°', width=5, command=lambda v=v:self.rotation.set(v)).pack(side='left')
        ttk.Label(self.simframe, text='竖起角：0° 平放 / 90° 竖直').pack(anchor='w', pady=(8,0))
        tk.Scale(self.simframe, from_=0, to=90, orient='horizontal', variable=self.tilt, length=260).pack(fill='x')
        self.scan(); self.protocol('WM_DELETE_WINDOW', self.close); self.after(50, self.poll)

    def scan(self):
        ports = [p.device for p in list_ports.comports()]; self.ports['values'] = ports
        if self.port.get() not in ports: self.port.set('COM7' if 'COM7' in ports else (ports[0] if ports else ''))

    def reset(self):
        self.detector = Orientation(); self.up = None; self.good = 0; self.last_good = 0
        self.details.set('等待有效姿态数据'); self.draw()

    def change_mode(self, event=None):
        if self.worker:
            self.mode.set('真实串口')
            messagebox.showinfo('请先断开', '请先断开串口，再切换模拟模式。'); return
        self.reset()
        self.status.set('模拟模式 · 不占用串口' if self.mode.get() == '模拟模式' else '未连接 · 无实时数据')

    def change_source(self, event=None): self.reset()

    def toggle(self):
        if self.worker:
            self.worker.stop_event.set(); self.connect.config(state='disabled'); self.status.set('正在断开…'); return
        if self.mode.get() != '真实串口':
            messagebox.showinfo('模拟模式', '先切换到真实串口模式。'); return
        if not self.port.get().strip():
            messagebox.showerror('串口', '请选择串口。'); return
        self.reset(); self.worker = Worker(self.port.get().strip(), 921600, self.events)
        self.worker.start(); self.connect.config(text='断开'); self.status.set('正在连接…')

    def poll(self):
        latest = None
        while True:
            try: typ, data = self.events.get_nowait()
            except queue.Empty: break
            if typ == 'snapshot': latest = data
            elif typ == 'connected': self.status.set('已连接 '+data+' · 等待数据')
            elif typ == 'error':
                self.status.set('连接失败'); messagebox.showerror('串口错误', data)
            elif typ == 'closed':
                self.worker = None; latest = None; self.connect.config(text='连接', state='normal')
                self.reset(); self.status.set('已断开 · 无实时数据')
                if self.closing: self.destroy(); return
        now = time.monotonic()
        if self.mode.get() == '模拟模式':
            self.up = simulated_up(self.rotation.get(), self.tilt.get())
            self.detector.update(self.up, now); self.show_data('模拟')
        elif latest and self.worker:
            proto, good, bad, rate, values = latest
            if good != self.good: self.last_good = now; self.good = good
            if now-self.last_good < 1 and self.last_good:
                keys = ('q_w','q_x','q_y','q_z') if self.source.get() == '姿态四元数' else ('acc_x','acc_y','acc_z')
                vals = [values.get(k) for k in keys]
                self.up = quaternion_up(vals) if len(keys) == 4 else acceleration_up(vals)
                self.detector.update(self.up, now, smooth=len(keys)==3)
                self.status.set(f'{self.port.get()} / 921600 · {proto or "未识别"} · 有效 {good} / 错误 {bad}')
                self.show_data(self.source.get())
        if self.mode.get() == '真实串口' and self.worker and self.last_good and now-self.last_good >= 1:
            self.up = None; self.details.set('数据超时 · 等待新数据'); self.status.set('数据超时 · 无实时状态'); self.draw()
        self.after(50, self.poll)

    def show_data(self, source):
        if self.up is None:
            self.details.set('来源：'+source+'\n等待有效数据'); self.draw(); return
        d = self.detector.current; flat = math.hypot(self.up[0], self.up[1]) < math.sin(math.radians(20))
        labels = {0:'0° 正常竖屏 → +X 顶',90:'90° 右转横屏 → −Y 左',180:'180° 倒竖屏 → −X 底',270:'270° 左转横屏 → +Y 右'}
        tilt = math.degrees(math.asin(min(1, math.hypot(self.up[0],self.up[1]))))
        a = '平放，角度不可靠' if flat else f'{angle(self.up):.1f}°'
        self.details.set(f'来源：{source}\n物理顺时针角：{a}\n竖起倾斜角：{tilt:.1f}°（0 平放）\n世界上（机身）：{self.up[0]:+.2f}, {self.up[1]:+.2f}, {self.up[2]:+.2f}\n四态：{labels.get(d, "未判定")}'+ ('（平放保持）' if flat else ''))
        self.draw()

    def draw(self):
        c = self.canvas; c.delete('all'); w,h = c.winfo_width(),c.winfo_height()
        if w < 10 or h < 10: return
        cx,cy = w/2,h/2; s = min(w/530,h/570)
        c.create_rectangle(cx-140*s,cy-245*s,cx+140*s,cy+245*s,fill='#263448',outline='#a8b8cf',width=4)
        c.create_rectangle(cx-122*s,cy-215*s,cx+122*s,cy+215*s,fill='#eaf3ff',outline='')
        c.create_text(cx,cy-230*s,text='+X 顶',fill='white',font=('Segoe UI',11,'bold'))
        c.create_text(cx+145*s,cy,text='+Y 右',fill='white',anchor='w')
        d = self.detector.current if self.up is not None else None
        if d is None:
            c.create_text(cx,cy,text='等待有效方向',fill='#43556d',font=('Microsoft YaHei',16)); return
        t = math.radians(-d)
        def p(x,y): return (cx+s*(x*math.cos(t)-y*math.sin(t)),cy+s*(x*math.sin(t)+y*math.cos(t)))
        points = [(-23,-20),(-23,-65),(-48,-65),(0,-120),(48,-65),(23,-65),(23,-20)]
        c.create_polygon(*[v for xy in points for v in p(*xy)],fill='#1670df')
        c.create_text(*p(0,5),text='UP',fill='#142c50',font=('Segoe UI',22,'bold'),angle=d)
        c.create_text(*p(0,43),text='12:34',fill='#142c50',font=('Segoe UI',18,'bold'),angle=d)
        for x,col in [(-55,'#f36c65'),(0,'#45ba86'),(55,'#f4b544')]:
            xx,yy=p(x,95); c.create_oval(xx-15*s,yy-15*s,xx+15*s,yy+15*s,fill=col,outline='')
        x,y=self.up[1],-self.up[0]; n=math.hypot(x,y)
        if n > .02:
            x,y=x/n*32*s,y/n*32*s
            ax,ay = cx+190*s,cy
            c.create_oval(ax-38*s,ay-38*s,ax+38*s,ay+38*s,outline='#52647a')
            c.create_line(ax,ay,ax+x,ay+y,fill='#65a9ff',width=3,arrow='last')
            c.create_line(ax,ay,ax-x,ay-y,fill='#ff6161',width=3,arrow='last')
            c.create_text(ax,ay+53*s,text='上 / 重力',fill='#c7d7ed')
        c.create_text(cx, h-15, text='固定机身视角：内容旋转，不是机身外框旋转', fill='#c7d7ed')

    def close(self):
        self.closing = True
        if self.worker: self.worker.stop_event.set()
        else: self.destroy()


def main(): PhoneDemo().mainloop()
if __name__ == '__main__': main()
