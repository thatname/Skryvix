# Skryvix

[English](README.md) | [中文](README.zh-CN.md)

Skryvix is an intelligent programming assistant system developed collaboratively by AI Coding Agents. This unique project is not just an AI-driven programming tool, but a system built entirely by AI Agents, showcasing innovative applications of AI in software development.

## Features

- **AI Native Development**: The entire project is collaboratively developed by AI Coding Agents, from architecture design to code implementation
- **Distributed Agent System**: Supports multiple AI Agents working in parallel to improve programming efficiency
- **Real-time Task Management**: Dynamic allocation and monitoring of programming tasks
- **Flexible Configuration System**: Supports customization of Agent behavior and workflows
- **WebSocket Real-time Communication**: Provides smooth real-time feedback and interaction experience

## System Architecture

Skryvix adopts a modern distributed architecture design:

- **Central Server**: WebSocket server based on FastAPI, responsible for task distribution and state management
- **Agent System**: Independent AI Coding Agents that can process multiple programming tasks in parallel
- **Real-time Communication**: Two-way real-time communication system based on WebSocket
- **State Management**: Complete task and Agent lifecycle management
- **Workspace Isolation**: Provides independent working directories for each Agent

## Main Functions

- **Multi-Agent Parallel Processing**: Supports multiple AI Agents working simultaneously
- **Real-time Task Assignment**: Intelligently assigns tasks to idle Agents
- **Progress Monitoring**: Real-time monitoring and display of task progress
- **Configuration Management**: Flexible Agent configuration system
- **Error Handling**: Comprehensive error handling and recovery mechanisms
- **Resource Management**: Intelligent process and resource management

## Installation and Usage

1. **Environment Requirements**
   - Python 3.8+
   - FastAPI
   - WebSocket support

2. **Installation Steps**
   ```bash
   # Clone repository
   git clone https://github.com/yourusername/skryvix.git
   cd skryvix

   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Configuration**
   - Copy `agent.yaml.example` to `agent.yaml`
   - Modify configuration file as needed

4. **Start Server**
   ```bash
   python server.py
   ```

5. **Access Interface**
   - Open browser and visit `http://localhost:8000`

## Configuration Guide

Main configuration items:
- `AGENT_CONFIG_PATH`: Agent configuration file path
- `AGENT_WORKDIR_BASE`: Agent working directory base path
- `AGENT_CONFIG_DIR`: Agent configuration directory

## Development Guide

Skryvix uses the following technology stack:
- FastAPI as backend framework
- WebSocket for real-time communication
- Async IO for concurrency handling
- Process management for Agent isolation

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Acknowledgments

Special thanks to all AI Coding Agents involved in development. Their collaboration made this project possible. This project not only demonstrates the potential of AI in software development but also provides new insights for future AI-driven development.