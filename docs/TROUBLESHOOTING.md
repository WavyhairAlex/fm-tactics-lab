# 故障诊断 · Troubleshooting

## 新电脑安装与换机

- 使用 Windows x64、完整的兼容 FM27 安装、Microsoft VC++ x64 运行库和 WebView2。桌面 EXE 自带 Python。
- 在引擎设置选择本机的游戏目录，并在存档对战中重新定位原始存档。要保留旧实验和手工译名，请退出工具后复制整个数据目录，再在设置中选择迁移后的目录。重要草稿请先另存为工具 JSON。
- 中国球员和外籍球员的中文名依赖存档姓名、游戏词库及用户导入的译名。缺少可靠匹配时显示原名。

## Setup on another PC

- Use Windows x64, a complete compatible FM27 installation, the Microsoft Visual C++ x64 runtime and WebView2. The desktop EXE includes Python.
- Select the local game folder in Engine Settings and locate your career save again. To reuse experiments and imported names, quit the app, copy its data directory, and select the copy in Settings. Export important drafts as tactic JSON before moving.
- Chinese player names use save data, game language resources and imported names. Players without a verified translation keep their original name.

## 暂不能模拟：关键接口或布局不匹配

展开引擎诊断，记录 `reason`、位置、工具版本与游戏构建。整体哈希不同不再单独导致运行拒绝，但关键入口、虚表、PE/TLS 或导入布局不匹配仍会阻止模拟。不能把所有这类错误视为已经修复。

构建阶段的 reference SHA256 不匹配属于另一条检查：首版只能从准确参考 DLL 生成比较基准，不允许把任意新 DLL 自动当成可信基准。

## 原生会话退出 82

宿主已经加载游戏 DLL，但初始化标志在约 10 秒内未就绪。比赛尚未进入正常模拟，不能据此判断战术配置有问题，也不能仅凭退出码认定是没有启动 Steam。先确认原游戏及 Steam 登录授权正常，再用 1 路并发复查。保留该任务 `worker_sessions` 下的 `session.jsonl` 与 `lifetime.json`。

## 一直显示“正在检查本地引擎”

这是 HTML 的初始占位文字，前端读取 `/api/status` 后才会替换。持续不变需要区分状态请求未结束和前端脚本未执行。先检查本地服务日志和浏览器请求。预检子进程有 30 秒超时，但文件读取和资源摘要计算不包含在这一超时内；不能简单认定 30 秒后整个检查必然结束。

找不到资源的正常结果会提供缺失原因，并允许在引擎设置中指定包含 `fm_Data` 与 `shared` 的游戏根目录。源码首版还必须先准备 README 列出的私有输入。

## 反馈时需要的信息

- 工具版本、游戏构建、Windows 版本和并发数。
- 最后成功的阶段、错误文本、引擎诊断原因及宿主退出码。
- 脱敏后的最小日志；不上传完整职业生涯存档、游戏 DLL 或浏览器资料。
