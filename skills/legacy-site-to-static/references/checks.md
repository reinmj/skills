# 检查工具约定

这些工具的通过范围是文件和已声明规则的一致性。用它们辅助项目验收，不能替代业务记录核对、完整安全审计、实际图片解码和浏览器功能验证。

## 来源盘点

`inventory_sources.py` 接受目录、ZIP 和普通文件。ZIP 只读条目元数据；SQL、SQL.GZ 和其他格式按文件登记，不解释正文、不展开。路径异常、大小写冲突和潜在噪声供审查，不自动删除或归档。

`--details` 输出条目清单，`--max-entries` 限制每个输入的报告范围，`--strict` 在截断或读取错误时返回非零。ZIP 中央目录由标准库先加载，所以该上限不是解析器的内存隔离。若 ZIP 特别大或不可信，另按资源预算处理。

## 公开版本检查

`--policy` 可传完整项目配置（读取 `validation`）或该对象本身。按实际数据模型填写，不能照抄示例路径。

| 字段 | 含义 |
| --- | --- |
| `required_pages` | 必须存在且已解析的 HTML 路径，默认 `index.html` |
| `indexable_pages` | 正式版需要允许收录的入口，默认首个必需页 |
| `require_indexing` | 默认 true；用户决定继续禁收录时设 false，不为过检查擅自开放 |
| `data_file`、`version_file` | 要核对的公开 JSON；填入后缺失或无法检查即失败 |
| `expected_version` | 期望版本，未填则不比对版本字符串 |
| `expected_counts` | 顶层集合名 → 期望数量；优先数 data 中数组，再比对 version 中计数 |
| `record_pages` | 集合、ID 字段、`{id}` 路径模板；核对每条记录是否有对应文件 |
| `translation_count_field` | version 中的确认译文计数字段，例如 `confirmedTranslations` 或项目现有字段 |
| `previous_confirmed_translations` | 从上一完整资料核实的数量基线；默认不猜测 |
| `translation_decrease_accepted` | 仅在用户明确接受内容变化时设 true，将数量下降改为警告 |
| `reviewed_static_config` | 已单独审查的静态服务配置精确路径，例如新写的 `.htaccess` |
| `public_download_archives` | 已审查确实拟公开的 ZIP 下载精确路径；不代表 ZIP 内部自动安全 |
| `allowed_post_form_actions`、`allowed_embed_urls` | 已核实的接收端和嵌入 URL；检查器不会提交表单或访问它们 |
| `extra_extensions`、`extra_public_files` | 业务需要的附加公开文件类型/路径，不会豁免服务端代码和敏感文件检查 |
| `directory_index` | 目录首页文件，默认 `index.html` |
| `max_files`、`max_total_bytes`、`max_text_bytes` | 默认 20000 文件、128 MiB 总量、每文件 4 MiB 文本扫描预算，可按项目调整 |

例如，集合为 `items`、稳定字段为 `legacy_id`、详情放 `catalog/ID/index.html`：

```json
{
  "data_file": "data/catalog.json",
  "version_file": "version.json",
  "expected_counts": {"items": 7},
  "record_pages": [{"collection": "items", "id_field": "legacy_id", "pattern": "catalog/{id}/index.html"}]
}
```

不用详情页的单页站移除该映射。多语言投影或复杂路由按实际产物分别建立清单，不猜测缺页不存在。工具检查文件存在，仍须核对页面实际呈现了对应名称、正文和图片。翻译数是版本里的声明值，审核状态及源摘要必须从完整资料复算。

引用按实际清单核对精确大小写，兼顾本地大小写不敏感、线上 Linux 敏感的差异。脚本解析常见 HTML 属性、srcset、内联样式和 CSS URL，不执行 JavaScript 动态路由；外部引用只计数，不自动访问。

报告不打印命中的凭据值；目录边界、文件哈希和内容元数据仍属于项目私有报告。`--out` 放在公开/输入目录之外，默认不覆盖已有文件；明确更新报告时用 `--overwrite`。预算或文本扫描限制会显示为错误/警告，不能把未扫描部分说成已验证。

## HTTP 核对

`probe_routes.py` 每次最多 20 个明确给出的 URL，默认每个 10 秒、响应正文最多读取 2 MiB。它不输出正文、Cookie 或查询参数值；响应被截断时不提供完整正文哈希，并视为未通过。

不会自动跟随跳转，便于分辨入口拦截、站内跳转和源站响应。`--expect-status` 对该次给出的所有 URL 生效，需要比较不同状态时分次调用。`--host-header` 仅用于普通 HTTP 源站诊断；HTTPS 使用能同时保留 Host/SNI 的工具，例如 `curl --resolve`，保持证书验证。

成功退出表示指定状态及读取范围符合预期，不表示内容业务正确；还要检查版本、页面内容和必要的视觉/交互行为。
