# cpu-15：GitHub 仓库与三组实验快速开始

本项目**只应在 cpu-15 宿主机**（`fyzhou@cpu-15`）执行，不要在 `root@ubuntu-fc-uvm` guest 中执行。实验不会管理服务器现有的 AgentENV 进程。

## A. 从已有 GitHub 仓库 Clone（一次）

真实源代码仓库：<https://github.com/pe0-p1e/agentvm-memory>，已有 `main`、`exp/balloon`、`exp/free-page-reporting` 三个实验分支。**当前仓库是 Public**；如果要上传未脱敏的实验日志，请先确认实验室允许公开。

在 cpu-15 的 host shell 执行：

```bash
cd ~/agentvm-memory
git remote set-url origin https://github.com/pe0-p1e/agentvm-memory.git
git config --local credential.helper 'cache --timeout=7200'
git fetch origin
git ls-remote origin HEAD
python3 -m unittest discover -s tests -v
```

你所在实验室网络对 `github.com:22` 和 `ssh.github.com:443` 连接会直接 reset；因此**不用继续尝试 SSH key**。我们已经让三个实验分支的 `publish_results.sh` 支持 HTTPS。

GitHub 网页上创建一个 **Fine-grained personal access token**：<https://github.com/settings/personal-access-tokens/new>。资源所有者选 `pe0-p1e`，只允许仓库 `agentvm-memory`，仓库权限设为 **Contents → Read and write**，设置有效期。第一次 `git push` 提示时输入 GitHub 用户名 `pe0-p1e`，密码位置粘贴 token（不回显）。不要把 token 写在 remote URL、shell 命令、脚本或聊天中。

本地 `credential.helper cache` 只在内存中短暂缓存凭据（这里是 7200 秒），方便连续三次上传。如果需要每次输入，可不设置。若 HTTPS 也不通，就不要再尝试网络推送：先用 `./scripts/run_all.sh` 本地运行，然后通过 `scp` 把 `runs/` 的结果取回个人电脑，再由个人电脑推送。

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
