# 老官网静态化改造

[English](README.md) | 简体中文

`legacy-site-to-static` 是一份面向 AI Agent 的 Skill，用于把老旧企业展示站、产品目录站从 PHP、ASP 或旧 CMS 迁移成可维护的静态官网。

它把一次真实改造中用到的资料恢复、本地编辑、多语言、FTP 发布、入口切换和回退方法整理成工作流程，并附带三个只读检查工具。适合希望保留原有内容、风格和可用主机的项目。

**管理工具、翻译接入和 FTP 发布器需要由 Agent 按当前项目实现。仓库提供工作流程和检查脚本，不包含通用可安装后台。**

核心流程和检查脚本不依赖特定大模型 API。Agent 需要能够读取本地文件、按需运行脚本；自动发现、安装目录和调用语法由所用 Agent 工具决定。

## 安装和使用

下载仓库，或克隆到本地：

```bash
git clone https://github.com/reinmj/skills.git
```

如果 Agent 支持导入 Skill，将完整的 `skills/legacy-site-to-static` 文件夹导入其支持的目录，保留内部文件结构。具体安装方式以该 Agent 工具的说明为准。

也可以直接让 Agent 读取本地 `SKILL.md`。以下路径需替换为实际绝对路径：

```text
请读取 /path/to/skills/skills/legacy-site-to-static/SKILL.md，
并按其中的流程改造这个老官网。
源码在【源码位置】，数据库备份在【SQL 或压缩包位置】，
图片和网页备份在【备份位置】。
先只读评估，列出内容完整性、动态功能和部署链路，
再制作本地可核对的静态版本，保留现有内容和风格。
```

已有同名 Skill 时先核对版本，避免重复安装。远程上传和正式入口切换应遵循当前项目的授权范围。

## 适用范围

适合公司介绍、产品展示、新闻、案例、下载中心和多语言展示页面。可以评估已有源码、数据库备份和图片附件，再决定恢复与生成方式。

登录、订单、支付、会员资料、实时库存等业务需要后端。此类项目先拆分展示页面与动态业务，再选择保留、迁移或重建后端。联系表单也必须连接真实接收端。

## 改造流程

1. 核对资料来源，确认正文、图片、附件和语言内容分别以哪份资料为准。
2. 生成本地静态站，保留可核对的内容 ID、路由和视觉风格。
3. 按需要实现本地编辑、翻译译稿、人工确认和版本备份。
4. 检查公开目录，将管理资料、密钥和旧服务端程序留在非公开位置。
5. 在已授权范围内备份、测试发布、切换入口，并准备回退。
6. 验证真实域名、源站、内容版本、图片和关键交互，交付日常更新方法。

FTP 上传完成、主机启动、目录禁止执行脚本、代理放行和域名切换分别需要核对。带有 `preview` 的物理目录也可能已经承载正式官网。

## 目录

```text
skills/legacy-site-to-static/
  SKILL.md                    工作流程与适用边界
  agents/openai.yaml          可选的宿主界面元数据
  assets/                     通用项目配置示例
  references/                 恢复、管理、发布和检查说明
  scripts/                    三个检查工具及共用模块
tests/run_tests.py             使用合成资料的回归检查
docs/wechat-article.md         公众号介绍正文
docs/x-posts.txt               X 短帖和串文
```

## 单独运行检查工具

脚本只依赖 Python 3.9 及以上的标准库。以下命令在仓库根目录运行，路径应替换为当前项目的实际位置，报告目录应位于原始资料和公开网站目录之外。

```bash
# 盘点目录或 ZIP 元数据，不执行旧程序，也不自动解压
python3 skills/legacy-site-to-static/scripts/inventory_sources.py \
  /private/source /private/web-backup.zip \
  --out /private/reports/inventory.json

# 检查待上传的公开目录，按当前项目填写策略
python3 skills/legacy-site-to-static/scripts/check_release.py \
  /project/public --mode formal --policy /private/project.json \
  --out /private/reports/release.json

# 检查明确指定的网址，不自动跟随跳转
python3 skills/legacy-site-to-static/scripts/probe_routes.py \
  https://www.example.invalid/ \
  --out /private/reports/http.json
```

完整选项见各脚本的 `--help` 和 [检查工具约定](skills/legacy-site-to-static/references/checks.md)。域名示例不可访问，需要替换。

来源盘点工具不会解析 SQL 正文。发布检查会核对本地引用、大小写、文件清单、部分敏感文件特征，以及项目声明的内容规则；HTTP 工具核对响应状态和有限读取范围。这些检查不执行浏览器 JavaScript，也不替代正文核对、图片解码、实际业务验证或完整安全审计。

## 维护和验证

```bash
python3 -B tests/run_tests.py
```

回归检查使用临时合成资料和本地 HTTP 服务。环境存在 `openssl` 时，还会验证不受信任的 HTTPS 证书被拒绝。原始版本已在 macOS 的 Python 3.9 上运行通过；Windows 运行环境仍需单独验证。

静态化减少了公开服务端程序的攻击面，主机、访问账号、前置代理和本地管理工具仍需要维护。恢复版本时使用已验证的静态发布包，避免重新启用存在风险的旧后台。

本仓库不含原项目源码、数据库、媒体文件、连接账号或部署地址。项目实际资料、完整编辑备份和检查报告请保存在仓库之外。
