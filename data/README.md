# MatchLens 三版本合成事件流

这三份数据用于推理时回放、反例测试和缺失数据测试，不用于训练或微调。全部由本仓库的程序生成，球队、球员、事件和坐标均为虚构；不包含真实比赛素材，也不是主办方提供的官方数据。

## 交付内容

| 文件 | 观察到的比赛过程 | 总记录数 | 事件数 |
| --- | --- | ---: | ---: |
| `streams/stream-01.jsonl` | 压迫、两次回传、前场夺回，7 秒后射门被扑出 | 211 | 29 |
| `streams/stream-02.jsonl` | 相同压迫和回传开局，对手随后传出并向前推进，未被夺回 | 208 | 26 |
| `streams/stream-03.jsonl` | 与 01 相同的比赛；关键时段位置与压迫通道不可用，仍可观察夺回和射门事件 | 210 | 26 |

每份覆盖 90 秒，比赛钟从下半场 62:00 开始，含两队共 22 名带号码的球员，以及 181 帧、2 Hz 的全员和球位置采样。球场为 105 × 68 米；Atlas（A）沿 x 正方向进攻，Union（U）沿 x 负方向进攻。三个版本均没有进球。

01 和 02 在观察时刻 53,000 ms 的可见记录完全相同。系统此时只能说观察到了压迫和回传，不能提前知道稍后的成功或失败。03 在区间 `[35000,64000)` 隐去位置和压迫信息，58 帧 tracking 显式标记为 unavailable。它检验系统能否保留可确认的事实，同时放弃缺乏证据的战术结论。

中性文件名、统一比赛 ID 避免将“成功 / 失败 / 信息不足”的标签作为输入线索。每个文件是独立的反事实世界，不能将三条流混合入同一比赛状态。

## 原始记录契约

每行是一个 JSON 对象。所有记录都有：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 当前为 `1.0` |
| `record_type` | `metadata`、`event`、`tracking` 或 `coverage` |
| `id` / `match_id` | 流内唯一记录 ID / 比赛 ID |
| `event_time_ms` | 相对于片段起点的事件时间，毫秒 |
| `observed_at_ms` | 到达接收端的时间；此样本非元数据记录均延迟 80 ms |
| `source` | `synthetic_simulator` |

- `metadata`：球队、球员名单、号码、坐标系、进攻方向、初始比分和各通道状态。
- `event`：`carry`、`pass`、`pressure`、`recovery`、`shot`、`save`；包含球队、执行球员、半场、可用的位置和结果。传球/带球在完成时发出，另带 `start_time_ms` 和终点。射门在起脚时发出，不提前带有落点或结果；扑救另行发出。
- `tracking`：每 500 ms 一个全员位置、球位置和控球归属采样；不可用时将位置设为 `null`，不补成零坐标。
- `coverage`：通道可用状态的即时更新；35 秒的丢失通知不会提前透露 64 秒将恢复。

`position_status` 明确位置是 `observed` 还是 `unavailable`。压力事件来自合成器的情境设定，并由球员间距离检查一致性；没有运行视频识别模型。位移使用简单插值，不应将这些小样本称为完整的足球物理模拟或真实追踪精度基准。

## 固定窗口下应计算出的事实

观察时刻为 68,000 ms，统计事件窗口为 `[40000,68000]`。以下标签只供人阅读和离线断言，不能进入 Agent 提示词。

| 指标 | 01 | 02 | 03 |
| --- | ---: | ---: | ---: |
| Union 回传次数 | 2 | 2 | 不可确定 |
| Atlas 压迫事件数 | 3 | 3 | 不可确定 |
| Atlas 夺回次数 | 1 | 0 | 1 |
| Atlas 射门次数 | 1 | 0 | 1 |
| 夺回至同一控球链射门 | 7 秒 | 未观察到 | 7 秒 |
| Atlas 前场夺回次数 | 1 | 0 | 不可确定 |
| 进球数 | 0 | 0 | 0 |

回传定义：传球朝己方球门方向移动超过 1 米。前场夺回定义：在进攻三区夺回，即 A 的 x≥70 或 U 的 x≤35。时间顺序与空间证据可以支持战术推断，但不证明压迫是夺回的唯一原因。

03 可以输出“Atlas 夺回球权，7 秒后完成射门”，不能输出“没有压迫”“在前场夺回”或“两次回传被压迫逼出”。缺失应返回 `value:null, status:insufficient_data`，不能当成 0。

## 重建、校验与使用

在仓库根目录执行，无第三方 Python 依赖：

```bash
python3 scripts/generate_match_fixtures.py
python3 scripts/validate_match_fixtures.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
```

默认 seed 为 `20261027`；`manifest.json` 保存记录数和 SHA-256。相同 seed 可重建完全相同的文件。当前 seed 仅改变很小的横向坐标偏移，不能把不同 seed 冒充具有独立战术变化的泛化测试集。后续应独立改变动作顺序、球员角色、夺回位置和结局。

程序侧使用示例：

```python
from backend.fixture_tools import FixtureStream

tools = FixtureStream("data/streams/stream-01.jsonl").snapshot(68000)
metric = tools.calculate_metric("regain_to_shot_seconds", "A", 40000, 68000)
assert metric["value"] == 7.0
assert metric["evidence_ids"] == ["e018", "e022"]
```

Harness 只把冻结观察时刻的工具暴露给模型。`query_events`、`get_player_context`、`calculate_metric`、`compare_windows`、`get_evidence` 均受该时间边界约束；模型没有推进时钟或读取文件的工具。数据加载器在宿主进程中持有文件，未来记录不会进入模型上下文。

`../evals/fixture_expectations.json` 是独立离线答案；运行入口不读取它，也不读取本说明。旧前端 `dist/matches.js` 含预写解释，不用作新 Agent 的原始事件输入。

实际模型运行方法见 [纯 Harness 实施方案](../docs/HARNESS_PLAN.zh-CN.md)。当前页面通过本地后端及 SSE 接入这些数据，启动方式见根目录 README。


## 完整比赛扩展（schema 1.1）

`streams/match-day.jsonl` 使用 seed 83，可通过 `python3 scripts/generate_match_day.py` 重建。包含 13,553 条记录，其中 2,738 条事件；2 Hz 位置，90 分 6.5 秒比赛时间（另有 80 ms 到达延迟）。22 名首发、A17 替补；半场换边，换人后重新排列 3–2–5；传球失败、拦截、抢断、压迫、射门、扑救、进球与终场均有独立事件。该 seed 的终场比分是 Atlas 0–1 Union，25 次射门。

`full-match-manifest.json` 记录本次 SHA-256 与规模。原来的三个配对案例保持不变。校验器支持 schema 1.0、1.1，并将案例 04 的 schema 1.2 分派到独立校验器，检查动态上场名单、球员速度、半场不连续、球权归属和坐标。该模拟器提供足球结构与可检验动作链，不声称已拟合职业比赛的事件分布，也不是模型训练数据。

## 120 秒反击与 VAR 案例（stream 04，schema 1.2）

`streams/stream-04.jsonl` 根据 [已确认的设计](../case-design/120s-counterattack-var-design.zh-CN.md) 生成，覆盖下半场补时 90:00–92:00。共 319 条记录：1 条背景、77 条事件、241 帧全员追踪。双方各 9 名非门将完成成功传球，合计 18 人；25 次传球尝试中 24 次成功。事件包含三次球权转换、禁区干净铲断、三传反击、过门将、入网及越位复核。

外层格式沿用原案例，内部 B 队仍编码为 U。新增裁判、VAR、死球与身体部位证据采用 schema 1.2；网页后端已接入这些新增官方事件及03 唯一入口的 120 秒回放。90 秒入网时保持待判，仅在 115.08 秒收到最终确认后计为 0–1；120 秒结束片段，不表示比赛终场。

```powershell
python -X utf8 scripts/generate_stream_04.py
python -X utf8 scripts/validate_stream_04.py
python -X utf8 -m unittest discover -s tests -p test_stream_04.py -v
```

生成器只写案例 04 及 `stream-04-manifest.json`，不会重写前三例和原清单。[格式说明](../case-design/stream-04-format.zh-CN.md) 解释新增字段和可复现方式，`../evals/stream-04-expectations.json` 保存独立离线预期。
