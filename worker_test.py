from worker import Worker

# Example Worker implementation
class CustomWorker(Worker):
    def __init__(self, name):
        self.name = name
        
    def start(self, task, workspace):
        print(f"Worker {self.name} starting task: {task} in workspace: {workspace}")
        
    async def stop(self):
        print(f"Worker {self.name} stopping")

# Test code
if __name__ == "__main__":
    # Create configuration
    yaml_config = """
    class: worker_test.CustomWorker
    params:
      - "TestWorker1"
    """
    
    try:
        # Create worker instance using factory method
        worker = Worker.create(yaml_config)
        
        # Test methods
        worker.start("Test Task", "Test Workspace")
        worker.stop()
        
        print("\nTest successful!")

    except Exception as e:
        print(f"Test failed: {str(e)}")


    import os
    # Load YAML config for SubprocessWorker as a string
    config_path = os.path.join(os.path.dirname(__file__), "worker_configs", "subprocess_worker.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        yaml_config = f.read()
    try:
        worker = Worker.create(yaml_config)
        print("Worker instance created:", worker)
        print("Type:", type(worker))
        print("Test successful!")
    except Exception as e:
        print(f"Test failed: {str(e)}")
