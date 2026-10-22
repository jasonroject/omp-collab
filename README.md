# OMP Collab

[English](README.en.md) · MIT License

让 Codex 等主助手通过本机 [Oh My Pi (OMP)](https://github.com/can1357/oh-my-pi) 调用 DeepSeek 或其他已配置模型，分派独立任务，并在核查后合并结果。

```text
主助手拆分任务 → OMP 调用指定模型 → 保存答复 → 主助手核查 → 整合结果
```

这是一个 Agent Skill，附带零第三方依赖的 Python 调用脚本。适合独立审查、公式推导、方案比较、代码草稿。它不会自动把第二个模型的回答当作事实，也不会让两个助手同时修改项目文件。

## 安装

需要 Python 3.10+、已安装的 OMP，以及在 OMP 中可用的模型账号。OMP 在本机启动，模型推理可能使用远程服务并产生费用。本项目不会读取或保存你的 API 密钥，也不会替你安装 OMP 或修改模型配置。

```powershell
git clone https://github.com/jasonroject/omp-collab.git
```

把仓库里的整个 `skills/omp-collab` 文件夹复制到 Codex 技能目录：`~/.codex/skills/`，或你自定义的 `$CODEX_HOME/skills/`。保留 `scripts`、`assets` 和 `agents`，不要覆盖同名技能。安装后重新打开会话，让客户端发现新技能。

在 Codex 中可以这样说：

> 使用 $omp-collab，让本机 OMP 里的 DeepSeek 独立检查这段推导。你负责核查它的结论，再整合进方案。

其他支持 `SKILL.md` 的助手可以使用相同技能包；客户端安装目录可能不同。

## 命令行使用

先确认 OMP 可用、模型标识正确：

```text
omp --help
omp models find deepseek
```

从 `skills/omp-collab/assets/task-template.md` 创建任务说明，或者直接使用公开示例：

```text
python skills/omp-collab/scripts/omp_delegate.py --model deepseek/deepseek-flash --task examples/review-task.md --output .omp-collab-runs --timeout 180
```

模型名只是示例，请替换为你已配置的完整 `provider/model` 标识。`--omp` 可指定 OMP 原生可执行文件路径；不支持 `.cmd`、`.bat`、`.ps1` 包装脚本。脚本不会自行切换模型或重试付费请求。

每次调用产生独立目录，包含：

| 文件 | 内容 |
| --- | --- |
| `request.md` | 实际提交的任务 |
| `response.txt` | OMP 标准输出 |
| `stderr.txt` | 诊断信息 |
| `run.json` | 请求的模型、耗时、退出状态、待核查状态 |
| `review.md` | 主助手核查后自行记录的结论 |

`returned` 只表示程序正常退出且有输出，答案仍可能不完整或错误。主助手应核查引用、公式、单位和代码，然后记录采用、纠正和暂不采用的内容。模型之间意见一致不能代替证据。

## 第一版的范围

- 使用 CLI 参数关闭 OMP 内置工具、扩展、规则、技能、LSP 和会话保存；在新目录中执行每个任务。
- 通过参数数组启动程序，任务经文件传递，避免把任务文字拼入 shell 命令。
- 超时或 Ctrl-C 时尝试终止当前调用的进程树，并保存已获取的输出。清理额外最多耗时约10秒；清理失败会写入诊断，可能需要处理残留子进程。
- 使用现有 OMP 账号和可信配置。OMP 仍可能发现 MCP、自定义工具和用户或上级目录配置；`--no-tools` 不是关闭所有能力的总开关。具体依据见[兼容性说明](skills/omp-collab/references/compatibility.md)。
- 第一版要求第二模型仅返回文字，不调用工具；不提供强制沙箱或全部工具隔离。需要证据时由主助手提供来源并独立验证。
- 任务和日志可能包含私密信息。默认 `.omp-collab-runs/` 被 Git 忽略，自定义输出目录需自行排除。仓库不包含真实对话、研究数据、账号配置或密钥。

## 验证与开发

```text
python -m unittest discover -s tests -v
```

测试覆盖 UTF-8 输出、失败状态、超时、任务隔离以及参数传递。GitHub Actions 在 Windows 和 Linux 上运行离线测试，不需要模型账号。真实调用需要你的 OMP 配置，不能由离线测试证明可用。

维护者首次集成使用 Windows、Python 3.14 与 OMP 18.8.4。其他版本应先检查 CLI 参数兼容性。模型调用仅验证程序链路，不证明回答正确。

提交修改时，请附相关验证结果。请勿在 issue、PR 或日志中附带凭据、完整私有配置或未获授权的材料。

## 许可证

[MIT](LICENSE)。本项目独立于 OpenAI、DeepSeek 和 OMP；不包含 OMP 本体或任何模型权重。
