# 升级与回滚

> **English:** How to move to a newer second-take and how to go back. What survives an upgrade: `workspace/`, `config.local.json`, your own wordlist. What doesn't: nothing of yours — this library writes only into those three places.

升级本库不会动你项目里的东西。这份文件只回答四件事：什么会被保留、怎么升、怎么确认、怎么退回。

## 一、升级会动什么、不会动什么

| 位置 | 升级时 | 说明 |
|---|---|---|
| `workspace/`（`input/` `output/` `cache/`） | **不动** | 你的原文、成品、缓存都在这。本库只读不删 |
| `config.local.json` | **不动** | 工作区路径、项目配置。缺键会补默认值，已有的值不覆盖 |
| 你自己的词表（`--words` 指的那份） | **不动** | 它在你的项目里，不在本库 |
| 本库的代码与文档 | **整份替换** | 别在包内手改；改了会随下次升级丢掉 |
| `reports/` | 可留可删 | 证据页是历史记录，留着方便对比 |

一句话：**本库只往 `workspace/`、`config.local.json` 和 `reports/` 三个地方写**，升级就是把其余部分换掉。

tools/ 下的脚本整目录一起用；内部模块与同目录脚本相互依赖，别只拷其中一支。

## 二、怎么升

### A. 用 zip（推荐）

1. 到 [Releases](https://github.com/O2wuyanliuse/second-take/releases) 下新的 `second-take-x.y.z-win.zip`，解到**另一个空目录**（不要覆盖旧目录，出事好退）。
2. 把旧目录里的 `workspace/`、`config.local.json`（有就一起：`reports/`）拷进新目录。
3. 在新目录里跑：

   ```bash
   python tools/bootstrap.py --check    # 只查不写盘；已经把旧 workspace 拷过来了，这里应当是「可以开工」
   python tools/status.py               # 三句话：我在哪、能自动查多少、下一步
   ```

   如果 `--check` 报缺东西，说明新版多了必需项——按它逐条给的提示补，不用猜。

### B. 用 git clone

```bash
cd <repo>
git pull
python tools/bootstrap.py --check
```

`git pull` 不会碰 `workspace/` 与 `config.local.json`（都在 `.gitignore` 里）。

### 升级后要做的唯一一件事

看一眼 `workspace/开工报告.md`：新版把「我在哪 / 覆盖率 / 下一步」重算了一遍。覆盖率掉下来了，通常是新版加了判据（分母变大），不是你弄坏了。

## 三、怎么确认升到位了

三处对得上才算：

1. 根目录 `VERSION` 里的号 == 你下的那个 zip 名里的号；
2. `python tools/bootstrap.py --check` 最后一行的结论是 **可以开工**；
3. `python tools/status.py` 能正常打出三句话（不是报错）。

想看更细的：`python tools/doctor.py` 的「版本」与「工作区」两行。

## 四、怎么退回旧版

本库不写注册表、不装服务、不改系统设置，所以回退就是**把旧目录拿回来**：

1. 旧目录如果还在——直接用它，什么都不用做。
2. 旧目录已经不在了——重新下旧版本的 zip 解到空目录，再把 `workspace/` 与 `config.local.json` 拷回去。

**注意**：新版可能已经往 `workspace/` 里写过它自己的东西（比如 `开工报告.md`、`STATE.md`）。旧版不认识这些文件时通常忽略；真出问题就删掉 `workspace/开工报告.md`（它是自动生成的，删了会重写）。

## 五、跨大版本

- **0.5 → 0.6**：多了 `evidence.py`（证据页）与 `doctor.py`（体检）。`--check` 的判据没变，`workspace/` 结构没变，直接换即可。
- **0.6 → 1.0**：对外说法统一了，`status.py` 成了「给人看的那一页」，`gate/_gate.py` 的那些「绿几项／跳过几项」不再进用户视野。判据项数与 `workspace/` 结构没变，直接换即可。

以后有大版本改了目录结构，会先写在这一节，并且提供迁移脚本——**没有迁移脚本的版本，说明不需要迁移**。
