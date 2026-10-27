---
name: legacy-site-to-static
version: "1.0.0"
display_name: "老官网静态化改造"
display_name_en: "Legacy Website to Static"
description: "把老旧企业展示站、产品目录站从 PHP、ASP 或旧 CMS 迁移成可维护的静态官网，恢复原内容与图片，交付本地编辑、发布和域名切换方案。用于旧官网静态化改造、安全重开或替换失修后台；保留交易、登录等动态业务的独立处理边界。"
description_zh: "把老旧企业展示站、产品目录站从 PHP、ASP 或旧 CMS 迁移成可维护的静态官网，恢复原内容与图片，交付本地编辑、发布和域名切换方案。用于旧官网静态化改造、安全重开或替换失修后台；保留交易、登录等动态业务的独立处理边界。"
description_en: "Migrate aging corporate websites and product catalogs from PHP, ASP, or legacy CMS platforms to maintainable static sites. Recover content and media, and prepare local editing, publishing, and traffic cutover. Use for legacy-site modernization or reopening; handle login, orders, and payments separately."
---

# 老官网静态化改造

把可静态展示的官网恢复成能继续维护、发布和回退的站点。默认沿用现有内容、品牌和可用主机；根据项目选择本地编辑工具、发布方式和入口切换方式。不要把静态化等同于截图、爬一份首页或删除后台文件。

## 先确定当前任务

- 分清用户要的是只读评估、本地试作、测试发布、日常更新，还是正式域名切换。沿用已有授权；用户说“只查不改”时，只检查，不修改远程文件或重载服务。
- 优先从可访问的源码、备份、SSH 配置、已有发布记录和运行状态中找信息。只问仍缺少且会改变方案的问题；密码和翻译密钥在用户本地输入，不发到聊天。
- 创建 skill 或参考过去的项目，不授予操作任何旧项目服务器的权限。域名、SSH 别名、FTP 目录、系统保留目录和数据库表名都是当前项目配置。
- 若有登录、下单、支付、会员数据、实时库存等功能，先划清可迁移的展示页面和仍需后端的业务。不要悄悄移除功能或制作“假提交成功”的表单。

## 工作顺序

1. **确定资料来源和部署链路。** 建立源码、数据库、网页文件、图片/附件、当前静态版本的来源表；同时核对 DNS → CDN/代理 → 主机 → 物理目录。按 [资料评估与恢复](references/assessment-and-recovery.md) 判断缺失、过时和不适合直接升级的部分。
2. **先制作本地可核对版本。** 解析公开业务数据，映射稳定 ID 和附件，保留风格，生成可重建的静态站。需要编辑、多语言或自动发布时，按 [静态站与本地管理](references/site-and-manager.md) 实现，不要求每个项目都重做一套后台。
3. **在上传前检查内容和边界。** 从业务记录建立必需页面和资源映射，再对真正的公开目录执行 `check_release.py`。核对条数、正文、图片、版本、译文和索引；确认译文数量须结合完整资料的审核状态与源摘要复核，不能只相信版本文件里的声明值。私有完整编辑资料与公开站点快照分开保存。
4. **按已授权的阶段发布。** 先准备明确的目标、备份、差异和回退方法，再执行授权范围内的上传或切换。FTP、旧程序隔离、平台权限、Nginx 与正式入口按 [发布与切换](references/publishing-and-cutover.md) 处理。授权已经覆盖时不机械重复确认。
5. **验证真实访问并交付维护方法。** 对真实域名、源站和关键路径分别核对；状态码、内容版本和图片都要与本次版本一致。交付最新完整资料备份、公开发布包、发布记录、实际上传目录和恢复方式。

## 本项目需要填入的配置

以 [项目配置示例](assets/project-config.example.json) 为起点，仅保留适用字段。未知值保留为未知，不能从邮件域名、文件名或上一次项目推断。

至少记录：资料来源与权威版本、动态功能处置、语言和确认状态、公开/私有目录、发布目标是否已绑定正式域名、代理/源站、索引模式、验证路径和备份位置。配置里只存非秘密信息，不存密码、私钥或 API 密钥。

## 可直接使用的只读工具

脚本仅使用 Python 标准库，兼容 Python 3.9 及以上。它们辅助核对，不执行 PHP、导入数据库、上传 FTP 或修改服务器。

```bash
# 目录与 ZIP 元数据盘点；不解压，不打印文件正文。
python3 scripts/inventory_sources.py /path/to/source /path/to/backup.zip --out /private/work/inventory.json

# 检查可上传目录；formal 检查首页索引状态。报告含文件 SHA256 清单。
python3 scripts/check_release.py /path/to/public --mode formal --policy /path/to/project.json --out /private/work/release-check.json

# 少量 GET 探测，不自动跟随跳转，不打印响应正文或 Cookie。
python3 scripts/probe_routes.py https://www.example.invalid/ https://www.example.invalid/version.json --out /private/work/http-check.json
```

脚本路径相对于本 skill 所在目录，实际调用时使用该目录的绝对路径。探测工具默认期望 200；检查跳转时用 `--expect-status 301`。使用自定义内容模型或检查策略时阅读 [检查工具约定](references/checks.md)，CLI 选项见各脚本 `--help`。

这些检查不执行网页 JavaScript、不解码图片、不测试外部表单，也不替代完整安全审计。根据实际改动另做图像解码、浏览器或业务功能验证。

## 必须保持的几个事实

- **原程序已隔离**、**目录禁止脚本执行**、**站点已启动**、**代理已放行**、**正式域名已切换**是不同状态；文件已传上去不代表全部完成。
- 最新 SQL/网页备份不一定是当前源码里的内容；数据库缺少旧英文表，不等于可以宣称旧英文已完整恢复。
- 公开数据会主动过滤私有译稿。继续编辑使用最近的完整资料备份，不用初始试用包或公开 `site.json` 覆盖已有确认内容。
- 已确认内容的数量意外下降时先查来源差异，保存可恢复资料；不要把“上传成功”当成业务内容正确。
- 物理目录名字带 `preview` 也可能已经承载正式官网。绑定正式域名后，工具文案、上传目标和说明必须同步；之后上传会直接更新正式站。
- 不从“没搜到 webshell”推断旧系统安全；不把一般文件权限位当作服务端脚本禁用；不通过恢复有漏洞的 PHP 站来回退静态内容。

## 完成时说明

明确提供当前可访问的网址、内容版本、已验证的范围、语言覆盖情况、真实发布目录、备份与回退位置，以及仍需用户完成的内容工作。只有 HTTP 检查就说明 HTTP 检查，未做视觉或实际业务验证时不要宣称全部验收。
