from worker import Worker

# Example Worker implementation
class CustomWorker(Worker):
    def __init__(self, name):
        self.name = name
        
    def start(self, task, workspace):
        print(f"Worker {self.name} starting task: {task} in workspace: {workspace}")
        
    def stop(self):
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