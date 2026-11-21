# Security Policy · 安全政策

**English summary:** This repository is a set of local Python scripts. It sends nothing anywhere, listens on no public port, and runs with your own permissions. Report issues through GitHub's private **Report a vulnerability** entry — no bounty, no response-time promise, no security mailbox.

> 这个仓库会在**你自己的机器上**跑 python、读写你的工作区、调 git。
> 你有权在跑之前知道边界在哪。这一页就是那份边界，不写口号。

## 一、它会不会联网

**默认不出网，没有遥测，没有自动检查更新。**

- `gate/`、`packaging/`、`tools/` 里的脚本不发起外部请求。自证：`git grep -n -e urlopen -e "requests\." -- gate packaging tools`——命中的是检测器里的**正则字符串**，不是请求。
- 出网只发生在**你自己敲的 git 命令**里：`clone`／`fetch`／`push`。
- 唯一的监听端口在 `tools/jimeng_bench/server.py`：`127.0.0.1:8765` 的**本地面板**，只绑回环，不对外。不跑它就不启动。

## 二、它会写哪里

- **仓库根**：`config.local.json`（`tools/bootstrap.py` 首次运行时从 `config.example.json` 生成）、`workspace/`（默认工作区，已在 `.gitignore` 里）。
- **工作区根及其子目录**：`input/`、`output/`、`cache/`。默认是 `<repo>/workspace`；你显式给 `--root` 或设 `SECOND_TAKE_HOME` 时，写到你指定的那个目录。
- **打包输出目录**：`packaging/_pack.py --out <目录>` 只往这里写。

**不写**：仓库外路径（除非你用 `--root`／`--out` 明确指定）、系统配置、注册表、家目录下的隐藏配置。

**一处会删东西，必须点名**：`_pack.py` 在硬闸不过（正文残留超限／验包不过／输出目录名不对）时会 `rmtree` 掉 `--out` 那个目录。它删的是自己刚建的产物，**不碰源文件**；但如果你把 `--out` 指到一个有资料的目录，那一目录会被清空。所以 `--out` 只给空目录或专用输出目录。

## 三、用什么权限跑

- 你的权限，与你运行它的用户同级。
- 不提权、不 `sudo`、不装系统服务、不改 `PATH`。
- 不下载可执行文件：仓库里没有二进制，发行包是 `git archive` 出来的纯文本 zip。

## 四、怎么报

**唯一渠道**：本仓库 → `Security` 标签 → **Report a vulnerability**（GitHub 私密报告）。

- 不要开公开 issue 贴细节——公开那一刻，所有人都能用上它。
- 如果 Security 页里**没有**这个入口：说明仓库设置里 Private vulnerability reporting 没开。那是配置故障，请找维护者打开，不要退回公开 issue。

**这里没有的东西，别等**：没有漏洞赏金，没有响应时限承诺，没有安全邮箱。单人维护，写一个做不到的时限，比不写更坏。

## 五、这些不是漏洞，是设计

报之前先看一眼，省双方一轮：

- **骨架库门禁只覆盖 3/19**：跳过 15 项，因为它没有那些对象（正文、素材、项目词表）。跳过不算绿，但不是故障。
- **`packaging/_leakscan.py` 不给词表返回 2**：那叫「没查成」，不是「查干净了」。词表属于项目，本库不带。
- **词表文件自己会命中自己**：负向词典必须写出它禁的词，这是定义。
- **退出码 2＝提示档**：本地钩子与 CI 都显式放过它。
- **扫描器不判断语义**：它会多报，也会漏报。它保证的是「词表里的词没出现」，不是「这个仓库绝对干净」。

## 六、这一页会过期

改动联网行为、写盘位置、权限要求的人，**必须同改这一页**。这一条机器不查，只靠 review——写在这里，至少让人有机会看见。
