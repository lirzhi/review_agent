```markdown
# Ollama 安装与配置指南（Linux）

## 1. 适用范围

本文档适用于 Linux 环境下的 Ollama 安装、服务化运行、模型目录自定义以及基础验证。

## 2. 安装方式概览

支持两种方式：

- **默认安装**
  使用官方安装脚本，适合快速部署。

- **自定义安装**
  手动解压到指定目录，适合对程序目录和模型目录有明确要求的场景。官方手动安装示例是将压缩包解到 /usr，并用 systemd 将 ExecStart 指向 /usr/bin/ollama serve。

## 3. 默认安装

### 3.1 安装命令

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

官方 Linux 文档将以上命令作为标准安装方式。

### 3.2 验证安装

```bash
ollama --version
which ollama
```

官方文档给出的手动安装验证命令是 `ollama -v`；实际路径建议以 `which ollama` 结果为准。

### 3.3 默认路径说明

- **程序路径**：不要写死为某一个固定值，建议以 `which ollama` 的结果为准。官方 systemd 示例使用 `/usr/bin/ollama`，但官方卸载说明也明确提到可执行文件可能位于 `/usr/local/bin`、`/usr/bin` 或 `/bin`。
- **默认模型目录**：`/usr/share/ollama/.ollama/models`。

## 4. 自定义安装（示例：程序目录 /opt/ollama，模型目录 /opt/ollama-models）

### 4.1 目录规划

- **程序安装目录**：`/opt/ollama`
- **模型存储目录**：`/opt/ollama-models`

> **说明**：自定义安装时，目录必须使用绝对路径。例如应写 `/opt/ollama`，而不是 `ollama`。否则命令会在当前工作目录创建目录，和预期不一致。

### 4.2 创建目录

```bash
sudo mkdir -p /opt/ollama
sudo mkdir -p /opt/ollama-models
```

### 4.3 解压安装包

将 `ollama-linux-amd64.tar.zst` 放在当前目录后执行：

```bash
sudo tar --zstd -xvf ollama-linux-amd64.tar.zst -C /opt/ollama
```

官方手动安装示例是将包解到 `/usr`。如果改为自定义目录，核心原则不变：先解压，再根据实际解压结果确认 ollama 可执行文件路径。

### 4.4 确认可执行文件路径

```bash
find /opt/ollama -maxdepth 3 -name ollama -type f
```

理想情况下应看到类似结果：

```text
/opt/ollama/bin/ollama
```

如果实际路径不同，后续 ExecStart 也必须同步修改为真实路径。

## 5. 配置 systemd 服务

### 5.1 创建服务用户

```bash
sudo useradd -r -s /bin/false -U -m -d /usr/share/ollama ollama
sudo usermod -a -G ollama $(whoami)
```

这与官方 Linux 文档中的服务用户创建方式一致。

### 5.2 设置模型目录权限

```bash
sudo chown -R ollama:ollama /opt/ollama-models
sudo chmod 755 /opt
sudo chmod -R 755 /opt/ollama-models
```

如果自定义模型目录，运行服务的 ollama 用户必须对该目录具有可访问和可写权限，否则服务启动时会因为无法创建模型缓存目录而失败。这一点与你之前遇到的 permission denied 问题一致。

### 5.3 创建服务文件

编辑：

```bash
sudo nano /etc/systemd/system/ollama.service
```

写入以下内容：

```ini
[Unit]
Description=Ollama Service
After=network-online.target

[Service]
ExecStart=/opt/ollama/bin/ollama serve
User=ollama
Group=ollama
Restart=always
RestartSec=3
Environment="PATH=/opt/ollama/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
Environment="OLLAMA_MODELS=/opt/ollama-models"

[Install]
WantedBy=multi-user.target
```

其中：

- `ExecStart` 必须与实际二进制路径一致。
- `OLLAMA_MODELS` 用于指定模型下载与存储目录。

官方 systemd 示例中默认使用 `/usr/bin/ollama serve`，并说明自定义安装可通过编辑 systemd 或 override 文件注入环境变量。

### 5.4 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

这是官方推荐的服务化启动方式。

## 6. 推荐的自定义方式：使用 override 文件

对于已存在的 `ollama.service`，更推荐通过 systemd override 文件添加环境变量，而不是每次都直接修改主 service 文件。

执行：

```bash
sudo systemctl edit ollama
```

写入：

```ini
[Service]
Environment="OLLAMA_MODELS=/opt/ollama-models"
```

保存后执行：

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

官方 Linux 文档明确推荐通过 `systemctl edit ollama` 或 `/etc/systemd/system/ollama.service.d/override.conf` 进行自定义。

## 7. 验证安装结果

### 7.1 查看版本

```bash
/opt/ollama/bin/ollama --version
```

如果已将 `/opt/ollama/bin` 加入 PATH，也可以直接使用：

```bash
ollama --version
```

### 7.2 查看服务环境变量

```bash
systemctl show ollama --property=Environment
```

### 7.3 查看日志

```bash
journalctl -e -u ollama
```

`journalctl -e -u ollama` 是官方给出的日志查看方法。

### 7.4 测试本地服务是否可访问

```bash
curl http://127.0.0.1:11434/api/version
```

如果服务正常运行，应返回版本信息。官方文档将 Ollama 作为本地服务运行，并默认监听本地接口。相关 API 示例也使用 `http://localhost:11434`。

## 8. 下载与运行模型

### 8.1 拉取模型

```bash
/opt/ollama/bin/ollama pull qwen3.5:27b
```

### 8.2 运行模型

```bash
/opt/ollama/bin/ollama run qwen3.5:27b
```

`qwen3.5:27b` 当前在 Ollama 模型库标签页中可用。

## 9. 更新 Ollama

### 9.1 默认安装更新

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### 9.2 手动安装更新

```bash
curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst | sudo tar x -C /usr
```

官方 Linux 文档给出了以上两种更新方式；FAQ 也说明 Linux 上升级可直接重新执行安装脚本。

## 10. 常见问题

### 10.1 不要把默认模型目录写成 /usr/share/ollama-models

这是不正确的。官方 FAQ 给出的默认模型目录是：

```text
/usr/share/ollama/.ollama/models
```

### 10.2 不要把默认程序路径写死成唯一的 /usr/bin/ollama

官方 systemd 示例使用 `/usr/bin/ollama`，但官方卸载文档明确说明可执行文件也可能在 `/usr/local/bin` 或 `/bin`。因此文档中更稳妥的写法是：实际程序路径以 `which ollama` 为准。

### 10.3 自定义安装时，命令路径必须前后一致

如果服务使用的是：

```text
/opt/ollama/bin/ollama
```

那么测试、拉取模型、运行模型时也应统一使用这一套路径，除非你已经正确配置了 PATH。

## 11. 卸载（简要）

官方 Linux 文档给出的卸载流程包括：

1. 停止并禁用 ollama 服务
2. 删除 systemd service 文件
3. 删除可执行文件和库目录
4. 删除 ollama 用户、组和服务目录

如果是自定义安装路径，还应额外删除自定义程序目录和自定义模型目录。官方示例卸载命令适用于默认安装；自定义安装时要按你的实际路径删除。

---

```