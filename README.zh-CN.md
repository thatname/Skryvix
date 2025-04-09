# Skryvix

Skryvix 是一个由 AI Coding Agents 协作开发的智能编程助手系统。这个独特的项目不仅是 AI 驱动的编程工具，更是一个完全由 AI Agents 构建的系统，展示了 AI 在软件开发领域的创新应用。

## 项目特点

- **AI 原生开发**: 整个项目由 AI Coding Agents 协作完成，从架构设计到代码实现
- **分布式 Agent 系统**: 支持多个 AI Agent 并行工作，提高编程效率
- **实时任务管理**: 动态分配和监控编程任务
- **灵活的配置系统**: 支持自定义 Agent 行为和工作流程
- **WebSocket 实时通信**: 提供流畅的实时反馈和交互体验

## 系统架构

Skryvix 采用现代化的分布式架构设计：

- **中央服务器**: 基于 FastAPI 的 WebSocket 服务器，负责任务分发和状态管理
- **Agent 系统**: 独立的 AI Coding Agents，可并行处理多个编程任务
- **实时通信**: 基于 WebSocket 的双向实时通信系统
- **状态管理**: 完整的任务和 Agent 生命周期管理
- **工作空间隔离**: 为每个 Agent 提供独立的工作目录

## 主要功能

- **多 Agent 并行处理**: 支持多个 AI Agent 同时工作
- **实时任务分配**: 智能分配任务给空闲的 Agents
- **进度监控**: 实时监控和展示任务进度
- **配置管理**: 灵活的 Agent 配置系统
- **错误处理**: 完善的错误处理和恢复机制
- **资源管理**: 智能的进程和资源管理

## 安装和使用

1. **环境要求**
   - Python 3.8+
   - FastAPI
   - WebSocket 支持

2. **安装步骤**
   ```bash
   # 克隆仓库
   git clone https://github.com/yourusername/skryvix.git
   cd skryvix

   # 安装依赖
   pip install -r requirements.txt
   ```

3. **配置**
   - 复制 `agent.yaml.example` 到 `agent.yaml`
   - 根据需要修改配置文件

4. **启动服务器**
   ```bash
   python server.py
   ```

5. **访问界面**
   - 打开浏览器访问 `http://localhost:8000`

## 配置说明

主要配置项：
- `AGENT_CONFIG_PATH`: Agent 配置文件路径
- `AGENT_WORKDIR_BASE`: Agent 工作目录基础路径
- `AGENT_CONFIG_DIR`: Agent 配置目录

## 开发说明

Skryvix 使用以下技术栈：
- FastAPI 作为后端框架
- WebSocket 进行实时通信
- 异步 IO 处理并发
- 进程管理实现 Agent 隔离

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 致谢

特别感谢所有参与开发的 AI Coding Agents，他们的协作使这个项目成为可能。这个项目不仅展示了 AI 在软件开发中的潜力，也为未来的 AI 驱动开发提供了新的思路。