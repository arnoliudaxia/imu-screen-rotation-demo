import math
import queue
import time
import tkinter as tk
from collections import deque
from tkinter import ttk, filedialog, messagebox

from serial.tools import list_ports
from .worker import Worker


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('WHEELTEC IMU 串口监视器')
        self.geometry('1100x740')
        self.minsize(850, 620)
        self.events = queue.Queue()
        self.worker = None
        self.closing = False
        self.recording = False
        self.values = {}
        self.history = deque(maxlen=200)
        self.port = tk.StringVar()
        self.baud = tk.StringVar(value='921600')
        self.status = tk.StringVar(value='未连接')
        self.record_status = tk.StringVar(value='未录制')
        self.info = tk.StringVar(value='等待有效数据')
        self.make_ui()
        self.scan()
        self.protocol('WM_DELETE_WINDOW', self.close_app)
        self.after(50, self.poll)

    def make_ui(self):
        bar = ttk.Frame(self, padding=8); bar.pack(fill='x')
        ttk.Label(bar, text='串口').pack(side='left')
        self.ports = ttk.Combobox(bar, textvariable=self.port, width=14)
        self.ports.pack(side='left', padx=5)
        ttk.Button(bar, text='扫描', command=self.scan).pack(side='left')
        ttk.Label(bar, text='波特率').pack(side='left', padx=(12, 4))
        self.bauds = ttk.Combobox(bar, textvariable=self.baud, width=10,
                                 values=['921600', '460800', '230400', '115200', '57600', '38400', '9600'])
        self.bauds.pack(side='left')
        self.connect_button = ttk.Button(bar, text='连接', command=self.toggle_connection)
        self.connect_button.pack(side='left', padx=10)
        self.rec_button = ttk.Button(bar, text='开始 CSV 录制', command=self.toggle_record, state='disabled')
        self.rec_button.pack(side='left')
        ttk.Label(bar, textvariable=self.record_status).pack(side='left', padx=8)
        ttk.Label(self, textvariable=self.status, padding=(10, 2)).pack(fill='x')
        main = ttk.Panedwindow(self, orient='horizontal'); main.pack(fill='both', expand=True, padx=8, pady=4)
        left = ttk.Frame(main, padding=8); right = ttk.Frame(main, padding=4)
        main.add(left, weight=1); main.add(right, weight=2)
        ttk.Label(left, text='实时数值（最近有效值）', font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        ttk.Label(left, textvariable=self.info, justify='left', font=('Consolas', 10)).pack(anchor='nw', pady=10)
        ttk.Label(right, text='姿态示意：X 红 / 前向，Y 绿，Z 蓝；Rz(yaw) Ry(pitch) Rx(roll)').pack(anchor='w')
        self.model = tk.Canvas(right, bg='#101b2d', height=320, highlightthickness=0)
        self.model.pack(fill='both', expand=True)
        ttk.Label(right, text='最近约 20 秒欧拉角（°）：Roll 红 / Pitch 绿 / Yaw 蓝').pack(anchor='w', pady=(6, 0))
        self.plot = tk.Canvas(right, bg='#101b2d', height=200, highlightthickness=0)
        self.plot.pack(fill='both', expand=True)
        self.model.bind('<Configure>', lambda _: self.draw_model())
        self.plot.bind('<Configure>', lambda _: self.draw_plot())

    def scan(self):
        ports = [p.device for p in list_ports.comports()]
        self.ports['values'] = ports
        if not self.port.get() and ports: self.port.set(ports[0])

    def toggle_connection(self):
        if self.worker:
            self.worker.stop_event.set()
            self.status.set('正在断开…')
            self.connect_button.config(state='disabled')
            return
        try:
            baud = int(self.baud.get())
            if baud <= 0 or not self.port.get().strip(): raise ValueError()
        except ValueError:
            messagebox.showerror('参数错误', '请选择串口并输入有效波特率。'); return
        self.values = {}; self.history.clear(); self.info.set('等待有效数据')
        self.draw_model(); self.draw_plot()
        self.worker = Worker(self.port.get().strip(), baud, self.events)
        self.worker.start()
        self.connect_button.config(text='断开')
        self.status.set('正在连接…')

    def toggle_record(self):
        if not self.worker: return
        if self.recording:
            self.worker.commands.put(('stop_record', None))
        else:
            path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')])
            if not path: return
            self.worker.commands.put(('record', path))
        self.rec_button.config(state='disabled')

    def poll(self):
        latest = None
        while True:
            try: typ, data = self.events.get_nowait()
            except queue.Empty: break
            if typ == 'snapshot': latest = data
            elif typ == 'connected':
                self.status.set('已连接 ' + data + '；等待识别协议')
                self.rec_button.config(state='normal')
            elif typ == 'recording':
                self.recording = bool(data)
                self.record_status.set('录制中: ' + data if data else '未录制')
                self.rec_button.config(text='停止录制' if data else '开始 CSV 录制', state='normal')
            elif typ in ('error', 'record_error'):
                if typ == 'record_error':
                    self.recording = False; self.record_status.set('录制失败')
                    self.rec_button.config(text='开始 CSV 录制', state='normal')
                if not self.closing: messagebox.showerror('串口 / 录制错误', data)
            elif typ == 'closed':
                self.worker = None; self.recording = False
                self.record_status.set('未录制')
                self.rec_button.config(text='开始 CSV 录制', state='disabled')
                self.connect_button.config(text='连接', state='normal')
                self.status.set('已断开')
                latest = None
                if self.closing:
                    self.destroy(); return
        if latest:
            proto, good, bad, rate, self.values = latest
            self.status.set(f'协议: {proto or "未识别"}   校验成功: {good}   失败: {bad}   接收: {rate:.0f} B/s（连接平均）')
            self.update_values()
            if all(k in self.values for k in ('roll_deg', 'pitch_deg', 'yaw_deg')):
                self.history.append((time.monotonic(), *(self.values[k] for k in ('roll_deg','pitch_deg','yaw_deg'))))
            self.draw_model(); self.draw_plot()
        self.after(50, self.poll)

    def update_values(self):
        def fmt(k):
            v = self.values.get(k)
            return f'{v:10.4f}' if v is not None else '         —'
        groups = [('Euler (deg)', ('roll_deg','pitch_deg','yaw_deg'), ('roll','pitch','yaw')),
                  ('Quaternion (w,x,y,z)', ('q_w','q_x','q_y','q_z'), ('w','x','y','z')),
                  ('Acceleration (m/s²)', ('acc_x','acc_y','acc_z'), ('x','y','z')),
                  ('Gyroscope (rad/s)', ('gyro_x','gyro_y','gyro_z'), ('x','y','z')),
                  ('Magnetic raw (mGauss)', ('mag_x','mag_y','mag_z'), ('x','y','z')),
                  ('Mag normalized (unitless)', ('mag_norm_x','mag_norm_y','mag_norm_z'), ('x','y','z')),
                  ('Temperature (°C)', ('temperature_c',), ('temp',))]
        lines = []
        for title, keys, labels in groups:
            lines.append(title)
            fields = [f'{label}:{fmt(k)}' for k, label in zip(keys, labels)]
            lines.extend('  '.join(fields[i:i+2]) for i in range(0, len(fields), 2))
        self.info.set('\n'.join(lines))

    def draw_model(self):
        c = self.model; c.delete('all')
        w, h = c.winfo_width(), c.winfo_height()
        if not all(k in self.values for k in ('roll_deg','pitch_deg','yaw_deg')):
            c.create_text(w/2, h/2, text='等待欧拉角数据', fill='white'); return
        r,p,y = [math.radians(self.values[k] % 360) for k in ('roll_deg','pitch_deg','yaw_deg')]
        cr,sr,cp,sp,cy,sy = math.cos(r),math.sin(r),math.cos(p),math.sin(p),math.cos(y),math.sin(y)
        def project(v):
            x,z0 = v[0],v[2]
            yy = cr*v[1]-sr*z0; zz = sr*v[1]+cr*z0
            xx = cp*x+sp*zz; zz = -sp*x+cp*zz
            x2 = cy*xx-sy*yy; y2 = sy*xx+cy*yy
            # Fixed elevated camera with perspective.
            sx = .8*x2-.6*y2; depth = .6*x2+.8*y2
            sy2 = .75*zz-.45*depth; depth = .45*zz+.75*depth
            scale = min(w,h)*.32/(4-depth)
            return (w/2+sx*scale, h/2-sy2*scale)
        vertices = [(x,y,z) for x in (-1,1) for y in (-.65,.65) for z in (-.35,.35)]
        for i,a in enumerate(vertices):
            for j,b in enumerate(vertices):
                if j > i and sum(x != y for x,y in zip(a,b)) == 1:
                    c.create_line(*project(a), *project(b), fill='#c9d6e6', width=2)
        origin = project((0,0,0))
        for v,color,label in [((1.7,0,0),'#ff6161','X 前'),((0,1.4,0),'#58dc89','Y'),((0,0,1.2),'#65a9ff','Z')]:
            end = project(v); c.create_line(*origin,*end,fill=color,width=3,arrow='last')
            c.create_text(*end,text=label,fill=color,anchor='sw')

    def draw_plot(self):
        c = self.plot; c.delete('all'); w,h = c.winfo_width(),c.winfo_height()
        c.create_line(35,h/2,w-5,h/2,fill='#52647a')
        c.create_text(3,5,anchor='nw',text='+180°',fill='#9baabc')
        c.create_text(3,h-5,anchor='sw',text='−180°',fill='#9baabc')
        now = time.monotonic()
        for i,color in enumerate(('#ff6161','#58dc89','#65a9ff'),1):
            pts = []
            for row in self.history:
                x = w-5 - (now-row[0]) / 20 * max(1,w-40)
                if x < 35: continue
                val = max(-180, min(180, row[i]))
                pts.extend((x, h/2 - val/180*(h/2-10)))
            if len(pts) >= 4: c.create_line(*pts, fill=color, width=2)

    def close_app(self):
        self.closing = True
        if self.worker:
            self.worker.stop_event.set()
            self.status.set('正在关闭串口…')
        else: self.destroy()


def main():
    App().mainloop()


if __name__ == '__main__': main()
