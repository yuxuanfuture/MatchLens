# stream 04 数据格式与生成

[stream-04.jsonl](../data/streams/stream-04.jsonl) 根据 [120 秒设计](120s-counterattack-var-design.zh-CN.md) 生成。片段覆盖下半场补时 90:00–92:00，包含双方 18 名非门将球员成功出球，以及入网、越位初判、VAR 复核和最终确认。

## 与原文件相同的部分

- UTF-8 编码，一行一个 JSON 对象，行间没有逗号，文件外没有数组括号。
- 共用字段为 `schema_version`、`record_type`、`id`、`match_id`、`event_time_ms`、`observed_at_ms`、`source`。
- 记录类别继续使用 `metadata`、`event`、`tracking`、`coverage`。本例通道全程可用，因此没有额外 `coverage` 记录。
- 内部球队编码仍为 A、U，人类设计中的 B 队对应 U；球场、球员号码和单位与原流一致。
- 时间以片段起点为零，单位为毫秒。比赛时钟起点为 `5400000`，即 90:00。
- 每 500 毫秒采样一次，包含首尾共 241 帧，每帧均包含 22 名球员。
- 传球和带球在动作完成时提供结果；射门在起脚时不携带未来结果。

## 裁判与球状态扩展

本例声明 `schema_version=1.2`。新增的内容是裁判主体、判罚关联、VAR 阶段和死球状态；这些语义不能由原案例中的传球或压迫事件替代。

| 内容 | 表达方式 |
| --- | --- |
| 球员事件 | `player_id`、`team_id` 指向实际动作球员和球队 |
| 官方事件 | `type` 为 `offside_flag`、`decision` 或 `var`；`official_id` 指向背景中的裁判名单 |
| 判罚涉及的球员 | `subject_player_id`、`subject_team_id`；不把球员填成执行判罚的裁判 |
| 官方事件的球员主体 | `player_id=null`、`team_id=null`，位置为不可用；这不表示追踪通道中断 |
| 引用 | `evidence_ids`、`pass_id`、`shot_id`、`decision_id`、`supersedes` 关联已获知的事实或同一批到达的事实 |
| 全员追踪 | 保留 `ball`、`players`、`possession_team_id`，新增 `in_play`、`ball_state` |
| 身体部位 | 83 秒的追踪帧附有 `body_parts`，保存头、躯干和双脚的位置 |

`ball_state` 区分持球阶段 `in_play`、传球在途 `pass_flight`、松散球 `loose`、射门飞行 `shot_flight` 和死球 `dead`。传球在途不指定持球人，但保留进攻球队；松散球与死球不强行指定比赛控球队伍。死球期间 A1 可以捡球，物理持球不计入比赛控球或传球数。

当前网页后端的导入白名单尚未接入这些官方事件。本次交付是数据文件、生成器和离线验收，不代表网页已经支持完整的 VAR 判罚呈现。

## 入网与正式进球

| 片段时间 | 记录 | 当时可知的正式比分 |
| --- | --- | --- |
| 89.5 秒 | `s001` 射门 | 0–0 |
| 90 秒 | `s002` 射门结束，结果为球入网、有效性待判 | 0–0 |
| 90.5 秒 | `o001` 助理裁判举旗 | 0–0 |
| 92 秒 | `d001` 初判越位，进球无效；VAR 开始核查 | 0–0 |
| 115 秒 | `d002` 最终确认有效，替代初判的当前效力 | 到达后为 0–1 |

唯一的有效进球记录为 `g001`，其发生时间仍是 90 秒，获知时间为 115.08 秒，即 `event_time_ms=90000`、`observed_at_ms=115080`。重放必须同时按发生时间和到达时间过滤，因此不会提前显示有效进球。初判记录保留，不被覆盖或删除。

## 生成与校验

在工程根目录执行：

```powershell
python -X utf8 scripts/generate_stream_04.py
python -X utf8 scripts/validate_stream_04.py data/streams/stream-04.jsonl
python -X utf8 -m unittest discover -s tests -p test_stream_04.py -v
```

生成器只写 `stream-04.jsonl` 和它的独立清单，不重写前三个案例。动作与跑位锚点位于 `scripts/stream_04_scene.py`，序列化和判罚事件位于 `scripts/generate_stream_04.py`；没有模型调用、下载或训练。

可用 `--root` 指定另一个输出根目录，检查字节级复现：

```powershell
python -X utf8 scripts/generate_stream_04.py --root case-design/reproduction
```

[独立清单](../data/stream-04-manifest.json) 保存记录数和 SHA-256。[离线预期](../evals/stream-04-expectations.json) 来自已确认的设计，供验收使用，不进入运行时推理输入。
