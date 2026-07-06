# cloudflareCIDR

本仓库用于生成并维护 Cloudflare 相关的 IPv4 CIDR 列表，供 Clash 等代理软件使用。

## 项目内容

- CloudflareCIDR-main.py
  - 主脚本，定期从远端仓库下载 ASN-to-IP 的 ZIP 包，提取并筛选出指定 ASN 下的 ipv4-aggregated.txt 文件中的 IPv4 网段，验证并规范化 CIDR 后写入：
    - Clash/CloudflareCIDR.list（每行格式：IP-CIDR,<cidr>,no-resolve）
    - CloudflareCIDR.txt（纯 CIDR 列表，每行一个）
  - 校验要点：使用 Python 标准库 ipaddress 对 CIDR 进行解析与过滤（仅保留 IPv4），忽略注释与空行，去重并保持稳定顺序。
  - 下载来源：脚本默认使用 https://github.com/ipverse/asn-ip 的 master 分支 ZIP（配置在脚本中）。
  - 错误处理：包含网络错误、压缩文件错误、文件缺失的日志与返回码，脚本在失败时会以非零退出码结束以便 CI/Action 可以检测。

- .github/workflows/CloudflareCIDR.yml
  - GitHub Actions 工作流，用于定时（或手动触发）运行脚本并在有更新时提交生成的文件到仓库。工作流使用 actions/checkout 和 setup-python，并依赖仓库的默认 GITHUB_TOKEN 来推送变更。

- Clash/CloudflareCIDR.list
  - 供 Clash 使用的规则文件，格式为 `IP-CIDR,<cidr>,no-resolve`。

- CloudflareCIDR.txt
  - 纯 CIDR 列表（每行一个网段），便于其它工具或脚本使用。

## 运行原理（脚本实现要点）

1. 下载 ZIP 到临时目录并解压，优先选择解压后唯一或名字包含 `asn-ip` 的根目录。若找不到会返回错误。  
2. 在解压目录中查找 `as/` 目录，遍历包含的 ASN 子目录（脚本中通过 INCLUDED_ASNS 集合控制要包含的 ASN）。  
3. 逐个读取 `ipv4-aggregated.txt` 文件，忽略注释/空行，收集所有条目。  
4. 使用 ipaddress.ip_network(..., strict=False) 解析每个条目，只保留 IPv4 网络，忽略解析失败的条目并记录日志。  
5. 去重并按稳定顺序输出到 `Clash/CloudflareCIDR.list` 和 `CloudflareCIDR.txt`。  
6. 工作流运行脚本后会检测仓库是否有变更（git diff），若有则使用 GITHUB_TOKEN 提交并推送更新。

## 使用

- 手动运行：在仓库根目录执行 `python CloudflareCIDR-main.py`（需要安装 requests 库）。
- CI：工作流已配置，按计划运行并自动提交变更。

## 恢复与注意事项

- 本次仓库精简操作会将非必要文件移除（如果你同意）。在移除操作前本仓库的完整快照已保存在分支 `backup/prune-20260706-150800`，可以用于恢复。  
- 若你希望保留其他文件或对 README 内容有修改意见，请告知，我会在执行后续删除操作前先调整。

---

如果需要，我可以现在开始根据你之前授权的规则（保留 workflow、脚本、生成文件和 README）在 main 上移除其余文件并直接推送。