# Narratix Engine

Narratix Engine（NTX）是一款基于CSV脚本驱动的轻量级叙事游戏引擎，面向视觉小说、互动剧情和分支文本游戏开发。引擎通过结构化表格定义剧情逻辑、变量系统与流程控制，实现剧情、状态与表现的完全解耦。

系统支持条件判断、表达式计算、随机分支、变量驱动剧情推进，以及CG与角色立绘的动态切换。同时提供图形化运行环境与存档机制，兼顾快速原型开发与工程化部署需求。

该引擎特别适用于教学、实验性叙事设计、以及中小规模文字游戏项目的高效开发。

## 运行

安装依赖：

```bash
pip install -r requirements.txt
```

启动图形版：

```bash
python main.py
```

## 目录结构

```text
story.csv                         默认剧情脚本
main.py                           启动入口
gameengine.py                     CSV 剧情执行引擎
pygame_display.py                 Pygame 图形界面
csv_utils.py                      CSV 多编码读取工具
assets/images/                    中央 CG 图片
assets/portraits/                 角色头像与表情
assets/audio/                     BGM 音频
saves/save_slot_*.json            多档位存档
CSV剧情脚本设计说明书.docx          详细脚本文档
```

## 操作

- `空格` / `回车` / 点击屏幕：推进剧情
- 点击选项或按 `A/B/C/D`：选择
- 鼠标滚轮 / `PageUp` / `PageDown` / `↑` / `↓`：回看文本历史
- `F5`：存入当前档位
- `F9`：读取当前档位
- 点击 CG 下方的“存档”或“读档”：弹窗选择档位
- `Esc`：退出

## CSV 编码

引擎会自动尝试读取：

```text
utf-8-sig
utf-8
utf-16
utf-16le
utf-16be
gb18030
gbk
cp936
```

WPS / Excel 中文环境保存的 GBK、GB18030 CSV 也可以读取。

## CSV 表头

`story.csv` 需要包含：

```csv
chapter,line_id,command,target,condition,expression,next_true,next_false,text,options,text_effect,text_effect_param,text_animation_duration,image_filename,portrait_filename,bgm_filename
```

字段说明：

- `chapter`：章节编号，例如 `chapter_1`
- `line_id`：行标签，供跳转使用
- `command`：指令名
- `target`：说话人、变量名、跳转目标或 META 键
- `condition`：执行条件，空值表示始终执行
- `expression`：表达式、数值或概率
- `next_true` / `next_false`：条件或随机分支目标
- `text`：显示文本或 META 值
- `options`：选项列表
- `text_effect` / `text_effect_param`：文本效果及参数
- `text_animation_duration`：文字展开时长
- `image_filename`：中央 CG 文件名
- `portrait_filename`：右上角头像文件名
- `bgm_filename`：BGM 文件名

## 指令

支持：

```text
META
TEXT
SET
ADD
CALC
CHOICE
GOTO
IFGOTO
RAND
END
```

## META

`META` 用于设置界面和脚本元信息，建议放在章节开头。

常用键：

- `ui_title`：窗口和左侧标题
- `ui_subtitle`：左侧副标题
- `profile_name`：左侧档案名称
- `profile_status`：左侧档案状态
- `profile_portrait`：左侧大头像文件名
- `hidden_stats`：不显示在左侧的隐式变量
- `initial_bgm`：章节开始时播放的默认 BGM

示例：

```csv
chapter_1,meta_ui_title,META,ui_title,,,,,项目标题,,normal,,0,,,
chapter_1,meta_ui_subtitle,META,ui_subtitle,,,,,章节副标题,,normal,,0,,,
chapter_1,meta_profile_name,META,profile_name,,,,,档案名称,,normal,,0,,,
chapter_1,meta_profile_status,META,profile_status,,,,,档案状态,,normal,,0,,,
chapter_1,meta_profile_portrait,META,profile_portrait,,,,,profile.png,,normal,,0,,,
chapter_1,meta_hidden_stats,META,hidden_stats,,,,,"内部标记,结局分数",,normal,,0,,,
chapter_1,meta_initial_bgm,META,initial_bgm,,,,,theme.mp3,,normal,,0,,,
```

## 显示事件

### TEXT

显示一段剧情文本。

```csv
chapter_1,start,TEXT,角色A,,,,,这里是第一句文本。,,normal,,1.2,scene_01.png,role_a_normal.png,theme.mp3
```

### CHOICE

显示选项并暂停。

```csv
chapter_1,choice_01,CHOICE,选择,,,,,请选择下一步。,"A:选项一->route_a;B:选项二->route_b",normal,,0.6,,role_a_normal.png,
```

### END

结束剧情。

```csv
chapter_1,end_01,END,结局,,,,,剧情结束。,,normal,,1.0,ending_01.png,role_a_normal.png,
```

## 变量指令

### SET

设置变量：

```csv
chapter_1,init_value,SET,变量A,,0,,,,,normal,,0,,,
```

### ADD

增减变量：

```csv
chapter_1,,ADD,变量A,,5,,,,,normal,,0,,,
```

### CALC

计算变量：

```csv
chapter_1,,CALC,结局分数,,变量A + RAND(1,5),,,,,normal,,0,,,
```

左侧指标会自动扫描当前章节中 `SET`、`ADD`、`CALC` 的 `target`。写在 `META hidden_stats` 中的变量不会显示，但仍可用于条件和结局判定。

## 流程控制

### GOTO

```csv
chapter_1,,GOTO,next_label,,,,,,,,normal,,0,,,
```

### IFGOTO

```csv
chapter_1,check_value,IFGOTO,,变量A >= 10,,good_route,bad_route,,,,normal,,0,,,
```

### RAND

按概率跳转：

```csv
chapter_1,random_event,RAND,,,0.35,event_route,normal_route,,,,normal,,0,,,
```

## 表达式

`condition` 和 `expression` 支持：

- 数值：`55`、`-10`、`3.5`
- 变量：`变量A`、`结局分数`
- 运算：`+ - * / // % **`
- 比较：`>= <= == != > <`
- 逻辑：`and`、`or`
- 随机整数：`RAND(1,5)`、`RANDINT(-2,4)`、`RANDOM(1,5)`
- 随机浮点：`RANDFLOAT(0,1)`

未定义变量按 `0` 处理。

## 图片规则

中央 CG：

- 由 `image_filename` 控制
- 文件放在 `assets/images/`
- 为空时沿用上一张
- 按比例完整适配，不裁切
- 中央栏标题直接显示图片文件名去掉扩展名

示例：

```csv
scene_01.png
```

标题显示：

```text
scene_01
```

## 头像规则

左侧大头像：

- 由 `META profile_portrait` 控制
- 文件放在 `assets/portraits/`

右上角当前事件头像：

- 由 `portrait_filename` 控制
- 文件放在 `assets/portraits/`
- 为空时沿用上一张
- 可用于表情切换

示例：

```csv
role_a_normal.png
role_a_smile.png
role_a_angry.png
```

## BGM 规则

初始 BGM：

- 用 `META initial_bgm` 指定
- 文件放在 `assets/audio/`

事件 BGM：

- 用 `bgm_filename` 指定
- 填写后立即切换并循环播放
- 为空时继续上一首

示例：

```csv
chapter_1,start,TEXT,角色A,,,,,文本。,,normal,,1.2,scene_01.png,role_a.png,theme.mp3
chapter_1,next,TEXT,角色B,,,,,另一段文本。,,normal,,1.2,,role_b.png,
chapter_1,event,TEXT,角色A,,,,,音乐切换。,,normal,,1.2,scene_02.png,role_a.png,tension.mp3
```

## 存档

图形版支持多档位存读档：

- CG 下方的“存档”或“读档”会打开档位选择弹窗
- `F5` 存入当前档位
- `F9` 读取当前档位
- 在弹窗中点击某个档位后，该档位会成为当前档位

存档文件：

```text
saves/save_slot_1.json
saves/save_slot_2.json
saves/save_slot_3.json
```

存档会保存：

- 剧情位置
- 当前事件
- 变量和隐式变量
- META 信息
- 当前 CG
- 当前头像
- 当前 BGM
- 文本历史
- 当前选项状态

开发阶段如果大幅修改 CSV 标签结构，建议删除旧存档后重新测试。

## 模板

```csv
chapter,line_id,command,target,condition,expression,next_true,next_false,text,options,text_effect,text_effect_param,text_animation_duration,image_filename,portrait_filename,bgm_filename
chapter_1,meta_ui_title,META,ui_title,,,,,项目标题,,normal,,0,,,
chapter_1,meta_profile_name,META,profile_name,,,,,档案名称,,normal,,0,,,
chapter_1,meta_profile_portrait,META,profile_portrait,,,,,profile.png,,normal,,0,,,
chapter_1,meta_hidden_stats,META,hidden_stats,,,,,内部标记,,normal,,0,,,
chapter_1,meta_initial_bgm,META,initial_bgm,,,,,theme.mp3,,normal,,0,,,
chapter_1,init_value,SET,变量A,,0,,,,,normal,,0,,,
chapter_1,start,TEXT,角色A,,,,,第一段文本。,,normal,,1.2,scene_01.png,role_a_normal.png,theme.mp3
chapter_1,choice_01,CHOICE,选择,,,,,请选择。,"A:选项一->route_a;B:选项二->route_b",normal,,0.6,,role_a_normal.png,
chapter_1,route_a,ADD,变量A,,5,,,,,normal,,0,,,
chapter_1,,TEXT,角色A,,,,,选项一的结果。,,normal,,1.0,,role_a_smile.png,
chapter_1,,END,结局,,,,,结束。,,normal,,1.0,ending_01.png,role_a_smile.png,
```
