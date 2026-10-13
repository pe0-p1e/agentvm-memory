# cpu-15：GitHub 仓库与三组实验快速开始

本项目**只应在 cpu-15 宿主机**（`fyzhou@cpu-15`）执行，不要在 `root@ubuntu-fc-uvm` guest 中执行。实验不会管理服务器现有的 AgentENV 进程。

## A. 从已有 GitHub 仓库 Clone（一次）

真实源代码仓库：<https://github.com/pe0-p1e/agentvm-memory>，已有 `main`、`exp/balloon`、`exp/free-page-reporting` 三个实验分支。**当前仓库是 Public**；如果要上传未脱敏的实验日志，请先确认实验室允许公开。

在 cpu-15 的 host shell 执行：

```bash
git clone https://github.com/pe0-p1e/agentvm-memory.git ~/agentvm-memory
cd ~/agentvm-memory
python3 -m unittest discover -s tests -v
./scripts/setup_ssh.sh
```

在仓库网页 `Settings → Deploy keys → Add deploy key` 添加上一步打印的 `.pub` 公钥，勾选 `Allow write access`。私钥只保留在服务器，不要提交、发聊天或上传。之后：

```bash
git remote set-url origin git@github.com:pe0-p1e/agentvm-memory.git
GIT_SSH_COMMAND="ssh -i $HOME/.ssh/id_ed25519_fc_memory_lab -o IdentitiesOnly=yes" git ls-remote origin HEAD
```

首次 SSH 连接先按 GitHub 官方公布的指纹验证 host key。若 cpu-15 无法直连 GitHub 22 端口，需要另行配置 GitHub SSH over port 443。

## C. 执行实验并逐个上传结果

确认原来手动运行的 `/tmp/firecracker-fyzhou.socket` demo VM 已经正常关机，并且 `~/sandbox-study/firecracker/demo/` 内有 `vmlinux-*` 和 `*.ext4`。

```bash
cd ~/agentvm-memory
python3 -m unittest discover -s tests -v
./scripts/run_all.sh --publish
```

这个命令会串行运行：

1. `main`：baseline，仅 guest alloc/touch/free，不做 balloon；
2. `exp/balloon`：guest free 后执行 balloon 0→512→0 MiB；
3. `exp/free-page-reporting`：预启动时打开 free-page reporting，不主动 inflate balloon。

每组约需数分钟（guest boot 时间另计）；不会同时运行多台本实验 microVM。成功后每一组创建单独 `results/<run_id>` 远端分支，包含 metrics.csv、summary.json、metadata.json、validation.json、guest-console.log 和 firecracker.log。**不会上传 guest.ext4 / 私钥 / GitHub token**。

## D. 出错时如何定位

- `Failed to mount ...`：检查 rootfs 是否被旧 demo 使用；脚本只复制镜像再 loop mount 副本，禁止删除其他人的运行文件。
- `No /dev/kvm access`：应在 cpu-15 host 运行且有 KVM 权限。
- `Missing guest /usr/bin/python3`：demo guest 镜像需要 Python3。
- `Timeout waiting for guest marker`：检查 `runs/<id>/guest-console.log` 和 `firecracker.log`；不要凭空解释数据。
- 没有出现在 GitHub：检查 deploy key 是否勾选 write 和 `git remote -v` 是否为目标仓库。
- 任何 AgentENV 现存 VM 均不属于本实验，绝不运行 `pkill firecracker` 或 `docker system prune`。
