# Windows IMU 串口监视器

Python / tkinter 只读 GUI；唯一第三方运行依赖为 pyserial。支持自动识别 **FDILink** 和 **YESENSE 59 53 输出帧**，不发送命令、不配置设备、不自动尝试波特率。Canvas 绘制透视线框和滚动曲线，不需要 NumPy、OpenGL 等。

## 使用

1. 安装带 tkinter 的 Python 3.10+ 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)；首次运行需要网络下载 pyserial。Python 的 Windows 官方安装包通常包含 tkinter。
2. 双击 `启动.bat`，或在本目录运行 `uv run python -m imu_reader`。uv 将依赖安装到项目 `.venv`，不会全局 pip 安装。路径中有空格也可使用。
3. 关闭占用串口的其他软件，点“扫描”、选择端口和波特率，点“连接”。默认 **921600，8N1，无流控**。扫描只列举端口，不自动打开或发送数据。
4. 校验通过后显示协议和数值；选择 CSV 路径可开始录制。停止录制、断开或退出会关闭文件及串口。打开失败、拔线和录制出错会提示。

**背景与限制：** [Seeed WHEELTEC H30 仓库](https://github.com/Seeed-Projects/WHEELTEC-H30-IMU) 提供 YESENSE 例程，教程常用 460800；此前对此处实际 COM7 数据的只读采样在 921600 校验通过的是 FDILink 0x40/0x41，而非 59 53。本软件支持两种协议，但此前仅 FDILink 已做硬件采样验证；YESENSE 只经合成帧测试。本次验收使用新 Worker 在 COM7/921600 只读采集约 3 秒，快照计数有效帧 623、坏帧 0，CSV 记录 624 行（其中 311 行含完整欧拉角）；停止后线程退出、CSV 和串口均可重新打开。快照是定期更新的，计数与最终 CSV 行数不必完全一致。自动单元测试不访问真实端口；不能由协议推断实物型号或固件。实际方向、轴定义和设备安装方向仍需用户验证。

## 独立手机自动转屏 Demo

双击 `启动手机转向Demo.bat`，或运行 `uv run python -m imu_reader.phone_demo`。与读取器是独立窗口；扫描选择串口（优先 COM7），固定 921600，只读，不发送配置。串口不能与读取器同时占用。先断开才能切换到不占串口的模拟模式；拖动物理顺时针角和竖起角，或用四个按钮测试。外框始终固定表示机身，屏幕内容旋转；蓝箭头是世界上方向在机身平面的投影，红箭头方向相反，是重力投影。竖起角 0° 为平放，90° 为竖直。

安装约定：手机面向前方时，屏幕前 −Z、顶 +X、右 +Y。物理顺时针角 0/90/180/270° 分别对应内容朝向机身 +X/−Y/−X/+Y 边；与内容相对于机身的旋转方向不要混淆。平放投影小于 sin(20°) 时保持原方向；跨越 45° 边界再加 12° 迟滞并持续 250 ms 才切换。初次有效方向直接判定。

默认使用 wxyz 四元数、假定 R 为 body→nav，世界上方向为 +Z，计算 Rᵀ·up。可手动选择低通的 −a 演示：此前 FDILink 静止实测 R·a 约为 [0,0,−g]，运动加速度会干扰；YESENSE 符号及姿态约定须实机确认，不自动套用加速度回退。来源无有效值时不显示实时方向；一秒没有新有效帧即超时。Worker 保留最近字段，若设备继续发送其他有效帧但停止发送所选字段，该字段无法单独超时，请注意检查协议输出。首次使用请实际转动设备核对安装轴、四元数顺序和方向，演示并非操作系统自动转屏控制。

## 显示与录制

- 校验成功/失败是本次连接期间的候选帧计数；失败包括 CRC、帧尾或 TLV 长度错误。随机噪声不会逐字节计为失败。速率是连接以来平均接收字节数/秒（B/s），不是帧率。
- 数值面板保留同一协议的最近有效字段。FDILink 的 IMU 和 AHRS 常为交替帧，因此这些字段不一定同时采样；切换协议或重连清空。设备不输出的字段显示“—”，旧数据不会自动超时清除。
- Euler：roll/pitch/yaw 度；FDILink 载荷弧度转度。YESENSE 0x40 次序是 pitch、roll、yaw。四元数显示 w,x,y,z；FDILink 直接采用结构的 Qw,Qx,Qy,Qz；YESENSE 按 q0,q1,q2,q3 显示并将 q0 视为 w（应在目标设备核验约定）。
- 3D 直接使用显示的 Euler，以 Rz(yaw) Ry(pitch) Rx(roll) 旋转模型；红 X 标为模型前向，绿 Y、蓝 Z。未收到 Euler 时不显示姿态；不使用四元数推算 Euler，不做 ROS 驱动的可选坐标系变换。此示意不是设备物理前向的保证。
- 加速度 m/s²；陀螺仪统一 rad/s：FDILink 原为 rad/s，YESENSE 原为 deg/s，已转换。原始磁场 mGauss（mG）；YESENSE 归一化磁场单独显示无量纲；温度 °C。
- 曲线约 20 秒，绘图范围 ±180°，超出只在图上截断，原始数字和 CSV 不截断。UI 约 10 Hz 更新，串口和 CSV 在后台线程处理。
- CSV UTF-8 BOM，固定列，`host_time` 是接收到校验帧时主机 UTC 时间（ISO 8601，毫秒），每个有效帧一行；**只记录该帧实际含有的字段**，缺失留空，不把上一帧的值伪装成同步值。`device_time_us` 是对应帧时间戳（YESENSE 0x51 或 FDILink）；不同协议的时间基准不保证相同。文件选择后会覆盖同名文件。写入错误会停止录制并提示；极慢磁盘可能拖慢后台采集并导致系统串口缓冲区丢数据。
- 自动识别仅依据有效校验帧；未知 FDILink 类型校验并计数但不解码，未知 YESENSE TLV 安全跳过。噪声中的伪头部若指示较长但尚未到齐的帧，解析可能暂时等待最多一个协议帧长度。只支持上述输出帧，不解析 YESENSE 配置应答。

## 资料与校验

- [YESENSE 官方 Python 例程](https://github.com/Seeed-Projects/WHEELTEC-H30-IMU/blob/main/6.Routines%20related%20to%20the%20inertial%20navigation%20module/3.Python%20routine/Yesense_Decode.py)；[YESENSE 通信协议英文 PDF](https://github.com/Seeed-Projects/WHEELTEC-H30-IMU/blob/main/1.User%20Manual/4.YESENSE%20Communication%20Protocol%20Document%EF%BC%88English%EF%BC%89.pdf)，2.1 节和示例明确单位、TLV 与校验。
- FDILink 参考 [结构](https://github.com/NDHANA94/ros2_wheeltec_n100_imu/blob/master/include/wheeltec_n100_imu/fdilink_data_struct.h)、[驱动](https://github.com/NDHANA94/ros2_wheeltec_n100_imu/blob/master/src/imu_node.cpp)、[CRC 表](https://github.com/NDHANA94/ros2_wheeltec_n100_imu/blob/master/src/crc_table.cpp)。CRC8 为 poly 0x31、反射 0x8c、init 0；CRC16/XMODEM 为 poly 0x1021、init 0，载荷 CRC16 高字节在前。测试将每个 8 位输入与该驱动两张完整查找表逐项对照。
- YESENSE 使用 CK1/CK2 双累加校验（并非 CRC 多项式），覆盖 TID 到 payload 末尾。两种协议均先校验完整帧再解码；流解析处理碎片、粘包及重同步。

## 补充实机验收

在 Windows 上以 COM7 / 921600 只读连接，识别 FDILink；验收时校验成功 2440、失败 0。仅验证当时的显示与接收，不代表长期稳定性或物理轴方向已校准；没有发送设备配置指令。

## 测试

```bat
uv run python -m unittest discover -s tests -v
```

测试不访问任何真实端口；还使用假串口验证异步 CSV 和关闭。真实设备的 USB 驱动、位姿方向、长期连续采集和高负载磁盘表现需要现场验收。打开串口可能由操作系统或 USB 驱动短暂改变 RTS/DTR 电平，虽然程序不写任何协议字节且请求两线为低电平。
