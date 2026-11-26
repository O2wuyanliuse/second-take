# _style 基线违规清单（2026-11-26 动手前）

共 151 条；此清单是工作清单，不是豁免清单。真豁免只有 templates 故意重复（b-2 标注后认）。

```
﻿Agent框架/_style_fingerprint.py: 模块 docstring 22 行 > 15
Agent框架/_style_fingerprint.py:106: main 87 行 > 80
gate/_e0.py: 模块 docstring 35 行 > 15
gate/_e0.py:50: 裸 except Exception: pass 未写吞的理由
gate/_gate.py: 模块 docstring 58 行 > 15
gate/_gate.py:336: main 173 行 > 80
gate/_gate.py:85: 裸 except Exception: pass 未写吞的理由
gate/_links.py: 模块 docstring 31 行 > 15
gate/_links.py:248: main 99 行 > 80
gate/_links.py:47: 裸 except Exception: pass 未写吞的理由
gate/_orphan.py: 模块 docstring 20 行 > 15
gate/_orphan.py:128: main 111 行 > 80
gate/_pname.py: 模块 docstring 29 行 > 15
gate/_pname.py:47: 裸 except Exception: pass 未写吞的理由
gate/_redline.py: 模块 docstring 33 行 > 15
gate/_redline.py:56: 裸 except Exception: pass 未写吞的理由
packaging/_doctor.py: 模块 docstring 22 行 > 15
packaging/_doctor.py:32: 裸 except Exception: pass 未写吞的理由
packaging/_dupcheck.py: 模块 docstring 47 行 > 15
packaging/_dupcheck.py:63: 裸 except Exception: pass 未写吞的理由
packaging/_leakscan.py: 模块 docstring 30 行 > 15
packaging/_leakscan.py:295: main 138 行 > 80
packaging/_leakscan.py:42: 裸 except Exception: pass 未写吞的理由
packaging/_leakscan.py:246: 裸 except Exception: pass 未写吞的理由
packaging/_nounlist.py: 模块 docstring 19 行 > 15
packaging/_nounlist.py:38: 裸 except Exception: pass 未写吞的理由
packaging/_pack.py: 模块 docstring 54 行 > 15
packaging/_pack.py:740: main 264 行 > 80
packaging/_pack.py:76: 裸 except Exception: pass 未写吞的理由
packaging/_pr_guard.py: 模块 docstring 29 行 > 15
packaging/_pr_guard.py:89: main 90 行 > 80
packaging/_pr_guard.py:42: 裸 except Exception: pass 未写吞的理由
packaging/_quote_scan.py: 模块 docstring 33 行 > 15
packaging/_quote_scan.py:51: 裸 except Exception: pass 未写吞的理由
packaging/_quote_scan.py:104: 裸 except Exception: pass 未写吞的理由
packaging/_scope_check.py: 模块 docstring 20 行 > 15
packaging/_scope_check.py:33: 裸 except Exception: pass 未写吞的理由
packaging/_sync_check.py: 模块 docstring 21 行 > 15
packaging/_sync_check.py:33: 裸 except Exception: pass 未写吞的理由
packaging/_sync_check.py:114: 裸 except Exception: pass 未写吞的理由
packaging/_triage.py: 模块 docstring 19 行 > 15
packaging/_triage.py:115: main 90 行 > 80
packaging/_triage.py:31: 裸 except Exception: pass 未写吞的理由
packaging/_verify_package.py: 模块 docstring 71 行 > 15
packaging/_verify_package.py:168: main 548 行 > 80
packaging/_verify_package.py:92: 裸 except Exception: pass 未写吞的理由
rules/_rule.py: 模块 docstring 22 行 > 15
templates/checks/_depmap.py: 模块 docstring 19 行 > 15
templates/checks/_diff.py: 模块 docstring 33 行 > 15
templates/checks/_diff.py:51: 裸 except Exception: pass 未写吞的理由
templates/checks/_links.py: 模块 docstring 31 行 > 15
templates/checks/_links.py:43: 裸 except Exception: pass 未写吞的理由
templates/checks/_mvchecks.py:101: main 108 行 > 80
templates/checks/_orphan.py: 模块 docstring 20 行 > 15
templates/checks/_orphan.py:145: main 111 行 > 80
tools/_keyout.py: 模块 docstring 21 行 > 15
tools/_keyout.py:30: 裸 except Exception: pass 未写吞的理由
tools/_mkview.py: 模块 docstring 37 行 > 15
tools/_mkview.py:56: 裸 except Exception: pass 未写吞的理由
tools/_mkview_flow.py: 模块 docstring 43 行 > 15
tools/bootstrap.py:33: 裸 except Exception: pass 未写吞的理由
tools/bootstrap.py:214: 裸 except Exception: pass 未写吞的理由
tools/build_public_package.py:91: 裸 except Exception: pass 未写吞的理由
tools/check_maintenance.py: 模块 docstring 20 行 > 15
tools/doctor.py: 模块 docstring 16 行 > 15
tools/evidence.py: 模块 docstring 20 行 > 15
tools/jimeng_bench/server.py: 模块 docstring 23 行 > 15
tools/jimeng_bench/server.py:388: 裸 except Exception: pass 未写吞的理由
tools/release.py: 模块 docstring 25 行 > 15
tools/release.py:43: 裸 except Exception: pass 未写吞的理由
tools/status.py:38: 裸 except Exception: pass 未写吞的理由
tools/verify_release.py:178: main 201 行 > 80
tools/verify_release.py:25: 裸 except Exception: pass 未写吞的理由
Agent框架/_style_fingerprint.py:42: 同名函数 collect 跨文件重复，未标 故意重复
packaging/_pack.py:606: 同名函数 collect 跨文件重复，未标 故意重复
tools/evidence.py:108: 同名函数 collect 跨文件重复，未标 故意重复
gate/_e0.py:169: 同名函数 selftest 跨文件重复，未标 故意重复
packaging/_dupcheck.py:143: 同名函数 selftest 跨文件重复，未标 故意重复
packaging/_quote_scan.py:249: 同名函数 selftest 跨文件重复，未标 故意重复
gate/_gate.py:212: 同名函数 run 跨文件重复，未标 故意重复
rules/_rule.py:187: 同名函数 run 跨文件重复，未标 故意重复
tests/helpers.py:52: 同名函数 run 跨文件重复，未标 故意重复
tools/verify_release.py:55: 同名函数 run 跨文件重复，未标 故意重复
gate/_links.py:134: 同名函数 load_allow 跨文件重复，未标 故意重复
packaging/_leakscan.py:98: 同名函数 load_allow 跨文件重复，未标 故意重复
templates/checks/_links.py:93: 同名函数 load_allow 跨文件重复，未标 故意重复
gate/_links.py:157: 同名函数 walk_md 跨文件重复，未标 故意重复
gate/_orphan.py:51: 同名函数 walk_md 跨文件重复，未标 故意重复
templates/checks/_links.py:118: 同名函数 walk_md 跨文件重复，未标 故意重复
templates/checks/_orphan.py:68: 同名函数 walk_md 跨文件重复，未标 故意重复
gate/_links.py:167: 同名函数 candidates 跨文件重复，未标 故意重复
templates/checks/_links.py:128: 同名函数 candidates 跨文件重复，未标 故意重复
gate/_links.py:202: 同名函数 scan_brackets 跨文件重复，未标 故意重复
templates/checks/_links.py:163: 同名函数 scan_brackets 跨文件重复，未标 故意重复
gate/_orphan.py:69: 同名函数 scan_py 跨文件重复，未标 故意重复
templates/checks/_orphan.py:86: 同名函数 scan_py 跨文件重复，未标 故意重复
packaging/_dupcheck.py:87: 同名函数 scan 跨文件重复，未标 故意重复
packaging/_quote_scan.py:128: 同名函数 scan 跨文件重复，未标 故意重复
packaging/_scope_check.py:85: 同名函数 scan 跨文件重复，未标 故意重复
packaging/_leakscan.py:59: 同名函数 die 跨文件重复，未标 故意重复
tools/_mkview_flow.py:92: 同名函数 die 跨文件重复，未标 故意重复
tools/check_maintenance.py:39: 同名函数 die 跨文件重复，未标 故意重复
packaging/_leakscan.py:64: 同名函数 load_words 跨文件重复，未标 故意重复
tools/review_gate.py:131: 同名函数 load_words 跨文件重复，未标 故意重复
packaging/_leakscan.py:258: 同名函数 scan_history 跨文件重复，未标 故意重复
tools/verify_release.py:121: 同名函数 scan_history 跨文件重复，未标 故意重复
packaging/_nounlist.py:135: 同名函数 load 跨文件重复，未标 故意重复
templates/checks/_mvchecks.py:26: 同名函数 load 跨文件重复，未标 故意重复
tests/test_review_gate.py:16: 同名函数 load 跨文件重复，未标 故意重复
packaging/_quote_scan.py:165: 同名函数 report 跨文件重复，未标 故意重复
tools/check_maintenance.py:103: 同名函数 report 跨文件重复，未标 故意重复
tools/verify_release.py:389: 同名函数 report 跨文件重复，未标 故意重复
packaging/_quote_scan.py:204: 同名函数 strip 跨文件重复，未标 故意重复
tools/asset_measure.py:33: 同名函数 strip 跨文件重复，未标 故意重复
packaging/_scope_check.py:57: 同名函数 iter_files 跨文件重复，未标 故意重复
packaging/_triage.py:104: 同名函数 iter_files 跨文件重复，未标 故意重复
templates/checks/_depmap.py:101: 同名函数 build 跨文件重复，未标 故意重复
tools/_mkview.py:179: 同名函数 build 跨文件重复，未标 故意重复
tools/_mkview_flow.py:326: 同名函数 build 跨文件重复，未标 故意重复
templates/checks/_diff.py:58: 同名函数 _load_cfg 跨文件重复，未标 故意重复
templates/checks/_links.py:49: 同名函数 _load_cfg 跨文件重复，未标 故意重复
templates/checks/_orphan.py:41: 同名函数 _load_cfg 跨文件重复，未标 故意重复
tests/helpers.py:22: 同名函数 git 跨文件重复，未标 故意重复
tools/check_maintenance.py:45: 同名函数 git 跨文件重复，未标 故意重复
tools/doctor.py:37: 同名函数 git 跨文件重复，未标 故意重复
tests/test_latest.py:17: 同名函数 vtuple 跨文件重复，未标 故意重复
tools/release.py:113: 同名函数 vtuple 跨文件重复，未标 故意重复
tests/test_manifest_no_export_ignore.py:35: 同名函数 translate 跨文件重复，未标 故意重复
tools/build_public_package.py:26: 同名函数 translate 跨文件重复，未标 故意重复
tools/_mkview.py:90: 同名函数 split_row 跨文件重复，未标 故意重复
tools/_mkview_flow.py:99: 同名函数 split_row 跨文件重复，未标 故意重复
tools/_mkview.py:101: 同名函数 is_sep 跨文件重复，未标 故意重复
tools/_mkview_flow.py:108: 同名函数 is_sep 跨文件重复，未标 故意重复
tools/bootstrap.py:29: 同名函数 utf8_stdio 跨文件重复，未标 故意重复
tools/status.py:34: 同名函数 utf8_stdio 跨文件重复，未标 故意重复
tools/bootstrap.py:114: 同名函数 git_out 跨文件重复，未标 故意重复
tools/seal.py:50: 同名函数 git_out 跨文件重复，未标 故意重复
tools/check_maintenance.py:87: 同名函数 verdict 跨文件重复，未标 故意重复
tools/evidence.py:169: 同名函数 verdict 跨文件重复，未标 故意重复
tools/doctor.py:48: 同名函数 pytest_available 跨文件重复，未标 故意重复
tools/evidence.py:51: 同名函数 pytest_available 跨文件重复，未标 故意重复
tools/evidence.py:232: 同名函数 render 跨文件重复，未标 故意重复
tools/status.py:131: 同名函数 render 跨文件重复，未标 故意重复
tools/release.py:96: 同名函数 sh 跨文件重复，未标 故意重复
tools/review_gate.py:41: 同名函数 sh 跨文件重复，未标 故意重复
tools/review_gate.py:208: 同名函数 cmd_check 跨文件重复，未标 故意重复
tools/seal.py:102: 同名函数 cmd_check 跨文件重复，未标 故意重复
tools/seal.py:37: 同名函数 sha256_of 跨文件重复，未标 故意重复
tools/verify_release.py:83: 同名函数 sha256_of 跨文件重复，未标 故意重复
tools/seal.py:33: 同名函数 find_git 跨文件重复，未标 故意重复
tools/verify_release.py:35: 同名函数 find_git 跨文件重复，未标 故意重复
违规 151 条
```