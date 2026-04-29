# Narratix Engine

Narratix Engine (NTX) is a lightweight, CSV-driven narrative game engine designed for visual novels, interactive storytelling, and branching text-based experiences. It enables developers to define story logic, variables, and control flow through structured tabular data, achieving a clean separation between narrative design and runtime execution.

The engine supports conditional branching, expression evaluation, randomized events, and variable-driven progression, along with dynamic CG and character portrait rendering. It also provides a graphical runtime environment and save/load system, making it suitable for rapid prototyping as well as structured production workflows.

Narratix Engine is particularly well-suited for educational use, experimental narrative design, and small-to-medium scale story-driven game development.

## Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the graphical version:

```bash
python main.py
```

## Project Structure

```text
story.csv                         Default story script
main.py                           Entry point
gameengine.py                     CSV story execution engine
pygame_display.py                 Pygame graphical interface
csv_utils.py                      Multi-encoding CSV reader
assets/images/                    Center CG images
assets/portraits/                 Character portraits and expressions
assets/audio/                     BGM audio files
saves/save_slot_*.json            Multi-slot save files
```

## Controls

- `Space` / `Enter` / click the screen: advance the story
- Click a choice or press `A/B/C/D`: choose an option
- Mouse wheel / `PageUp` / `PageDown` / `Up` / `Down`: scroll text history
- `F5`: save to the current slot
- `F9`: load from the current slot
- Click `Save` or `Load` under the CG area: open the slot selection dialog
- `Esc`: exit, or close the slot dialog when it is open

## CSV Encoding

The engine automatically tries these encodings:

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

CSV files saved by WPS or Excel in Chinese Windows environments, such as GBK or GB18030 files, are also supported.

## CSV Header

`story.csv` must contain:

```csv
chapter,line_id,command,target,condition,expression,next_true,next_false,text,options,text_effect,text_effect_param,text_animation_duration,image_filename,portrait_filename,bgm_filename
```

Field reference:

- `chapter`: chapter ID, for example `chapter_1`
- `line_id`: row label used as a jump target
- `command`: command name
- `target`: speaker, variable name, jump target, or META key
- `condition`: execution condition; empty means always run
- `expression`: expression, value, or probability
- `next_true` / `next_false`: targets for conditional or random branches
- `text`: displayed text or META value
- `options`: choice list
- `text_effect` / `text_effect_param`: text effect and its parameter
- `text_animation_duration`: text reveal duration
- `image_filename`: center CG filename
- `portrait_filename`: top-right portrait filename
- `bgm_filename`: BGM filename

## Commands

Supported commands:

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

`META` sets interface and script metadata. It is usually placed at the start of a chapter.

Common keys:

- `ui_title`: window title and left-panel title
- `ui_subtitle`: left-panel subtitle
- `profile_name`: left-panel profile name
- `profile_status`: left-panel profile status
- `profile_portrait`: left-panel large portrait filename
- `hidden_stats`: variables hidden from the left panel
- `initial_bgm`: default BGM played when the chapter starts

Example:

```csv
chapter_1,meta_ui_title,META,ui_title,,,,,Project Title,,normal,,0,,,
chapter_1,meta_ui_subtitle,META,ui_subtitle,,,,,Chapter Subtitle,,normal,,0,,,
chapter_1,meta_profile_name,META,profile_name,,,,,Profile Name,,normal,,0,,,
chapter_1,meta_profile_status,META,profile_status,,,,,Profile Status,,normal,,0,,,
chapter_1,meta_profile_portrait,META,profile_portrait,,,,,profile.png,,normal,,0,,,
chapter_1,meta_hidden_stats,META,hidden_stats,,,,,"internal_flag,ending_score",,normal,,0,,,
chapter_1,meta_initial_bgm,META,initial_bgm,,,,,theme.mp3,,normal,,0,,,
```

## Display Events

### TEXT

Displays a story text entry.

```csv
chapter_1,start,TEXT,Character A,,,,,This is the first line.,,normal,,1.2,scene_01.png,role_a_normal.png,theme.mp3
```

### CHOICE

Displays choices and pauses.

```csv
chapter_1,choice_01,CHOICE,Choice,,,,,Choose your next step.,"A:Option One->route_a;B:Option Two->route_b",normal,,0.6,,role_a_normal.png,
```

### END

Ends the story.

```csv
chapter_1,end_01,END,Ending,,,,,The story ends here.,,normal,,1.0,ending_01.png,role_a_normal.png,
```

## Variable Commands

### SET

Set a variable:

```csv
chapter_1,init_value,SET,stat_a,,0,,,,,normal,,0,,,
```

### ADD

Increase or decrease a variable:

```csv
chapter_1,,ADD,stat_a,,5,,,,,normal,,0,,,
```

### CALC

Calculate a variable:

```csv
chapter_1,,CALC,ending_score,,stat_a + RAND(1,5),,,,,normal,,0,,,
```

The left-panel stats are scanned automatically from `target` values used by `SET`, `ADD`, and `CALC` in the current chapter. Variables listed in `META hidden_stats` are not displayed, but they can still be used in conditions and ending checks.

## Flow Control

### GOTO

```csv
chapter_1,,GOTO,next_label,,,,,,,,normal,,0,,,
```

### IFGOTO

```csv
chapter_1,check_value,IFGOTO,,stat_a >= 10,,good_route,bad_route,,,,normal,,0,,,
```

### RAND

Jump by probability:

```csv
chapter_1,random_event,RAND,,,0.35,event_route,normal_route,,,,normal,,0,,,
```

## Expressions

`condition` and `expression` support:

- Numbers: `55`, `-10`, `3.5`
- Variables: `stat_a`, `ending_score`
- Operators: `+ - * / // % **`
- Comparisons: `>= <= == != > <`
- Logic: `and`, `or`
- Random integers: `RAND(1,5)`, `RANDINT(-2,4)`, `RANDOM(1,5)`
- Random floats: `RANDFLOAT(0,1)`

Undefined variables are treated as `0`.

## Image Rules

Center CG:

- Controlled by `image_filename`
- Files are placed in `assets/images/`
- Empty values keep the previous image
- Images are fitted proportionally without cropping
- The center column title displays the image filename without its extension

Example:

```csv
scene_01.png
```

Displayed title:

```text
scene_01
```

## Portrait Rules

Left large portrait:

- Controlled by `META profile_portrait`
- Files are placed in `assets/portraits/`

Top-right current event portrait:

- Controlled by `portrait_filename`
- Files are placed in `assets/portraits/`
- Empty values keep the previous portrait
- Can be used for expression changes

Example:

```csv
role_a_normal.png
role_a_smile.png
role_a_angry.png
```

## BGM Rules

Initial BGM:

- Set with `META initial_bgm`
- Files are placed in `assets/audio/`

Event BGM:

- Set with `bgm_filename`
- A non-empty value switches immediately and loops the new track
- Empty values keep the previous track

Example:

```csv
chapter_1,start,TEXT,Character A,,,,,Text.,,normal,,1.2,scene_01.png,role_a.png,theme.mp3
chapter_1,next,TEXT,Character B,,,,,Another line.,,normal,,1.2,,role_b.png,
chapter_1,event,TEXT,Character A,,,,,The music changes.,,normal,,1.2,scene_02.png,role_a.png,tension.mp3
```

## Saves

The graphical version supports multiple save slots:

- Click `Save` or `Load` under the CG area to open the slot selection dialog
- `F5` saves to the current slot
- `F9` loads from the current slot
- After selecting a slot in the dialog, that slot becomes the current slot

Save files:

```text
saves/save_slot_1.json
saves/save_slot_2.json
saves/save_slot_3.json
```

Save data includes:

- Story position
- Current event
- Visible and hidden variables
- META data
- Current CG
- Current portrait
- Current BGM
- Text history
- Current choice state

During development, if you significantly change CSV labels or route structure, delete old save files before testing again.

## Template

```csv
chapter,line_id,command,target,condition,expression,next_true,next_false,text,options,text_effect,text_effect_param,text_animation_duration,image_filename,portrait_filename,bgm_filename
chapter_1,meta_ui_title,META,ui_title,,,,,Project Title,,normal,,0,,,
chapter_1,meta_profile_name,META,profile_name,,,,,Profile Name,,normal,,0,,,
chapter_1,meta_profile_portrait,META,profile_portrait,,,,,profile.png,,normal,,0,,,
chapter_1,meta_hidden_stats,META,hidden_stats,,,,,internal_flag,,normal,,0,,,
chapter_1,meta_initial_bgm,META,initial_bgm,,,,,theme.mp3,,normal,,0,,,
chapter_1,init_value,SET,stat_a,,0,,,,,normal,,0,,,
chapter_1,start,TEXT,Character A,,,,,First line.,,normal,,1.2,scene_01.png,role_a_normal.png,theme.mp3
chapter_1,choice_01,CHOICE,Choice,,,,,Choose.,"A:Option One->route_a;B:Option Two->route_b",normal,,0.6,,role_a_normal.png,
chapter_1,route_a,ADD,stat_a,,5,,,,,normal,,0,,,
chapter_1,,TEXT,Character A,,,,,Result of option one.,,normal,,1.0,,role_a_smile.png,
chapter_1,,END,Ending,,,,,End.,,normal,,1.0,ending_01.png,role_a_smile.png,
```
