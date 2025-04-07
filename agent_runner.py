import asyncio
import websockets
import json
import argparse
import os
import sys
from agent import Agent  # Assuming agent.py is in the same directory or Python path

# --- Configuration ---
# Get agent config path from environment or use default from server.py
AGENT_CONFIG_PATH = os.getenv("AGENT_CONFIG_PATH", "config.yaml")

# --- Helper Functions ---
async def send_json(ws, data):
    """Safely send JSON data over WebSocket."""
    try:
        await ws.send(json.dumps(data))
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket connection closed while trying to send.")
    except Exception as e:
        print(f"Error sending JSON: {e}")

async def send_status_update(ws, agent_id, status):
    """Send a status update message to the server."""
    print(f"Agent {agent_id}: Sending status update - {status}")
    await send_json(ws, {"type": "status_update", "payload": {"agent_id": agent_id, "status": status}})

async def send_task_result(ws, agent_id, task_id, status, result):
    """Send the result of a completed/failed task to the server."""
    print(f"Agent {agent_id}: Sending task result for {task_id} - Status: {status}")
    await send_json(ws, {"type": "task_result", "payload": {"agent_id": agent_id, "task_id": task_id, "status": status, "result": result}})

# --- Main Agent Runner Logic ---
async def run_agent(agent_id: str, server_ws_url: str):
    """Initializes agent, connects to server, and handles tasks."""
    print(f"Agent {agent_id}: Initializing...")

    # 1. Initialize the Agent
    try:
        # Ensure the config path exists
        if not os.path.exists(AGENT_CONFIG_PATH):
             print(f"Error: Agent config file '{AGENT_CONFIG_PATH}' not found.")
             print("Ensure the config file exists or set the AGENT_CONFIG_PATH environment variable.")
             sys.exit(f"Agent {agent_id} cannot start: Config file '{AGENT_CONFIG_PATH}' not found.")

        # Load python-dotenv if available to get OPENAI_API_KEY etc.
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print(f"Agent {agent_id}: Loaded environment variables from .env")
        except ImportError:
            print(f"Agent {agent_id}: python-dotenv not installed, relying on system environment variables.")

        agent_instance = Agent.create(AGENT_CONFIG_PATH)
        print(f"Agent {agent_id}: Agent instance created successfully from {AGENT_CONFIG_PATH}.")
    except Exception as e:
        print(f"Agent {agent_id}: Failed to initialize agent - {e}")
        # Optionally notify server if possible, but likely can't connect yet
        return # Exit if agent can't be created

    # 2. Connect to Server WebSocket
    uri = f"{server_ws_url}/ws/agent/{agent_id}"
    print(f"Agent {agent_id}: Attempting to connect to server at {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Agent {agent_id}: Connected to server.")
            # Agent starts in 'idle' state implicitly upon connection (handled server-side)

            # 3. Listen for Messages (Tasks)
            while True:
                try:
                    message_str = await websocket.recv()
                    message = json.loads(message_str)
                    print(f"Agent {agent_id}: Received message: {message}")

                    if message.get("type") == "assign_task":
                        task_id = message.get("task_id")
                        task_description = message.get("description")

                        if not task_id or not task_description:
                            print(f"Agent {agent_id}: Received invalid task assignment.")
                            continue

                        print(f"Agent {agent_id}: Received task {task_id}: {task_description}")

                        # Update status to busy
                        await send_status_update(websocket, agent_id, "busy")

                        # Execute the task using the agent
                        task_result = None
                        task_status = "failed" # Default to failed
                        try:
                            # The agent.start() method is an async generator.
                            # We need to consume it to get the full response.
                            full_response = ""
                            async for token in agent_instance.start(task_description):
                                full_response += token
                                # Optional: Send intermediate progress updates if needed
                                # await send_json(websocket, {"type": "progress_update", "payload": {"agent_id": agent_id, "task_id": task_id, "token": token}})

                            task_result = full_response
                            task_status = "completed"
                            print(f"Agent {agent_id}: Task {task_id} completed successfully.")

                        except Exception as e:
                            print(f"Agent {agent_id}: Error executing task {task_id}: {e}")
                            task_result = f"Error during task execution: {str(e)}"
                            task_status = "failed"

                        # Send result back to server
                        await send_task_result(websocket, agent_id, task_id, task_status, task_result)

                        # Update status back to idle (server also does this on result receipt, but good practice)
                        await send_status_update(websocket, agent_id, "idle")

                    else:
                        print(f"Agent {agent_id}: Received unknown message type: {message.get('type')}")

                except websockets.exceptions.ConnectionClosedOK:
                    print(f"Agent {agent_id}: Server closed the connection normally.")
                    break
                except websockets.exceptions.ConnectionClosedError as e:
                    print(f"Agent {agent_id}: Server connection closed unexpectedly: {e}")
                    break
                except json.JSONDecodeError:
                    print(f"Agent {agent_id}: Received invalid JSON.")
                except Exception as e:
                    print(f"Agent {agent_id}: Error in message handling loop: {e}")
                    # Attempt to notify server of error before breaking?
                    try:
                        await send_status_update(websocket, agent_id, "error")
                    except Exception:
                        pass # Ignore if we can't even send status
                    break # Exit loop on general error

    except (websockets.exceptions.InvalidURI, websockets.exceptions.WebSocketException, ConnectionRefusedError) as e:
        print(f"Agent {agent_id}: Failed to connect to server at {uri} - {e}")
    except Exception as e:
        print(f"Agent {agent_id}: An unexpected error occurred: {e}")
    finally:
        print(f"Agent {agent_id}: Shutting down.")


# --- Script Entry Point ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Runner Process")
    parser.add_argument("--agent-id", required=True, help="Unique ID for this agent instance")
    parser.add_argument("--server-url", required=True, help="WebSocket URL of the management server (e.g., ws://localhost:8000)")
    args = parser.parse_args()

    print(f"Starting agent runner for Agent ID: {args.agent_id}")
    print(f"Connecting to Server URL: {args.server_url}")

    # Run the main async function
    try:
        asyncio.run(run_agent(args.agent_id, args.server_url))
    except KeyboardInterrupt:
        print(f"Agent {args.agent_id}: Received KeyboardInterrupt, shutting down.")
