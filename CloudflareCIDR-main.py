import os
import shutil
import zipfile
import requests
import re
import errno
import stat

url = "https://github.com/ipverse/asn-ip/archive/refs/heads/master.zip"
zip_name = "master.zip"

# 输出目录与文件
os.makedirs("Clash", exist_ok=True)  # 确保 Clash 目录存在
clash_path = os.path.join("Clash", "CloudflareCIDR.list")
cidr_path = "CloudflareCIDR.txt"

included_asns = ['209242', '13335', '149648', '132892', '139242', '202623', '203898', '394536']
ip_addresses = []


def _on_rm_error(func, path, exc_info):
    """错误回调：仅在文件已不存在(ENOENT) 时忽略；处理权限错误后重试，否则重新抛出。"""
    exc = exc_info[1]
    err_no = getattr(exc, 'errno', None)
    if err_no == errno.ENOENT:
        # 文件/目录已经不存在，忽略
        return
    if err_no == errno.EACCES:
        # 尝试移除写保护并重试一次
        try:
            os.chmod(path, stat.S_IWUSR)
            func(path)
            return
        except Exception:
            pass
    # 未知错误，重新抛出
    raise


def safe_rmtree(path):
    """安全地删除目录：存在时删除，race condition 或权限问题时尽量恢复。
    不会因目录在删除前被并发移除而抛出 FileNotFoundError。
    """
    try:
        if os.path.islink(path):
            # 处理符号链接
            os.unlink(path)
            return
        if os.path.isdir(path):
            shutil.rmtree(path, onerror=_on_rm_error)
    except FileNotFoundError:
        # 已被移除，忽略
        pass


try:
    # 下载 zip 文件
    r = requests.get(url, timeout=30)
    r.raise_for_status()  # 如果状态不是 200-299，会抛异常
    with open(zip_name, "wb") as f:
        f.write(r.content)

    # 解压 zip 到当前目录
    with zipfile.ZipFile(zip_name, 'r') as zip_ref:
        zip_ref.extractall(".")

        # 尝试从 zip 列表推断根目录（通常是 asn-ip-master 或 asn-ip-<sha>）
        names = zip_ref.namelist()
        root_dirs = [n.split('/')[0] for n in names if n and '/' in n]
        root_dirs = list(dict.fromkeys(root_dirs))  # 去重且保留顺序
        root = root_dirs[0] if root_dirs else "asn-ip-master"

    # 遍历 as 目录（注意使用 os.path.join）
    as_dir = os.path.join(root, "as")
    for root_dir, dirs, files in os.walk(as_dir):
        if 'ipv4-aggregated.txt' in files:
            asn = os.path.basename(root_dir)
            if asn in included_asns:
                with open(os.path.join(root_dir, 'ipv4-aggregated.txt'), 'r') as file:
                    ips = file.read().splitlines()
                    ip_addresses.extend(ips)

    # 匹配 IPv4/CIDR 的简单正则
    ipv4_regex = re.compile(r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})$')

    # 写入结果文件
    with open(clash_path, 'w') as clash_file, open(cidr_path, 'w') as cidr_file:
        for ip in ip_addresses:
            if ipv4_regex.match(ip):
                clash_file.write(f"IP-CIDR,{ip},no-resolve\n")
                cidr_file.write(f"{ip}\n")
            else:
                # 如果不是标准 CIDR，按原脚本保留一行（或可以改为跳过）
                clash_file.write(f"{ip}\n")

finally:
    # 清理下载和解压的文件夹，使用安全删除函数以避免 FileNotFoundError
    try:
        if os.path.isfile(zip_name):
            os.remove(zip_name)
    except Exception as e:
        print(f"Warning: 删除 {zip_name} 时出错: {e}")

    try:
        # 如果我们推断出的 root 存在则删除
        if 'root' in locals():
            safe_rmtree(root)
        # 兜底判断常见目录名：使用 ignore_errors=True，按用户要求（选项C）避免因目录不存在失败
        shutil.rmtree("asn-ip-master", ignore_errors=True)
    except Exception as e:
        print(f"Warning: 删除解压目录时出错: {e}")
