import os
import re
from typing import Optional, List

class WorkSpace:
    def __init__(self, manager: 'WorkspaceManager', id: int):
        """Initialize workspace

        Args:
            manager: Reference to workspace manager
            id: Workspace ID (non-negative integer)
        """
        self._manager = manager
        self.id = id
        self.taskid: Optional[str] = None

    @property
    def path(self) -> str:
        """Get workspace path"""
        return os.path.join(self._manager.work_root, f'ws{self.id}')

    @property
    def is_occupied(self) -> bool:
        """Check if workspace is occupied"""
        return self.taskid is not None


class WorkspaceManager:
    def __init__(self, work_root: str):
        """Initialize workspace manager

        Args:
            work_root: Root directory for workspaces
        """
        self.work_root = work_root
        self.workspaces: List[WorkSpace] = []
        self._scan_workspaces()

    def _scan_workspaces(self):
        """Scan workspace directories"""
        if not os.path.exists(self.work_root):
            os.makedirs(self.work_root)

        # Clear existing list
        self.workspaces.clear()

        # Scan all directories starting with 'ws'
        for item in os.listdir(self.work_root):
            if os.path.isdir(os.path.join(self.work_root, item)) and item.startswith('ws'):
                try:
                    workspace_id = int(item[2:])  # Extract number after 'ws'
                    workspace = WorkSpace(self, workspace_id)
                    self.workspaces.append(workspace)
                except ValueError:
                    continue  # Ignore invalid directory names

        # Sort by ID
        self.workspaces.sort(key=lambda ws: ws.id)

    def alloc(self, taskid: str) -> Optional[WorkSpace]:
        """Allocate an idle workspace

        Args:
            taskid: Task ID

        Returns:
            Allocated workspace, or None if no idle workspace available
        """
        for workspace in self.workspaces:
            if not workspace.is_occupied:
                workspace.taskid = taskid
                return workspace
        return None

    def free(self, workspace: WorkSpace) -> bool:
        """Free a workspace

        Args:
            workspace: Workspace to be freed

        Returns:
            Whether the workspace was successfully freed
        """
        if workspace in self.workspaces and workspace.is_occupied:
            workspace.taskid = None
            return True
        return False

    def create(self) -> Optional[WorkSpace]:
        """Create a new workspace

        Returns:
            Created workspace, or None if creation fails
        """
        # Find the smallest available ID
        used_ids = {ws.id for ws in self.workspaces}
        new_id = 0
        while new_id in used_ids:
            new_id += 1

        # Create new workspace
        try:
            workspace = WorkSpace(self, new_id)
            os.makedirs(workspace.path)
            self.workspaces.append(workspace)
            # Sort by ID
            self.workspaces.sort(key=lambda ws: ws.id)
            return workspace
        except OSError:
            return None

    def delete(self, workspace: WorkSpace) -> bool:
        """Delete a workspace

        Args:
            workspace: Workspace to be deleted

        Returns:
            Whether the workspace was successfully deleted
        """
        if workspace not in self.workspaces or workspace.is_occupied:
            return False

        try:
            os.rmdir(workspace.path)
            self.workspaces.remove(workspace)
            return True
        except OSError:
            return False

    def set_workspace_count(self, count: int) -> bool:
        """Set the number of workspaces

        Args:
            count: Desired number of workspaces

        Returns:
            Whether the number was successfully set
        """
        if count < 0:
            return False

        current_count = len(self.workspaces)

        # Need to delete excess workspaces
        if count < current_count:
            # Calculate how many workspaces need to be removed
            to_remove_count = current_count - count
            
            # Count available (unoccupied) workspaces
            available_workspaces = [ws for ws in self.workspaces if not ws.is_occupied]
            
            # If we don't have enough available workspaces to remove, return False
            if len(available_workspaces) < to_remove_count:
                return False
            
            # Sort available workspaces by ID in descending order
            # This way we remove higher numbered workspaces first
            available_workspaces.sort(key=lambda ws: ws.id, reverse=True)
            
            # Remove the required number of workspaces
            for i in range(to_remove_count):
                if not self.delete(available_workspaces[i]):
                    return False

        # Need to create new workspaces
        while len(self.workspaces) < count:
            if self.create() is None:
                return False

        return True


import shutil
import unittest
class TestWorkspaceManager(unittest.TestCase):
    def setUp(self):
        """测试前创建临时工作目录"""
        self.test_root = "test_workspaces"
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)
        os.makedirs(self.test_root)
        self.manager = WorkspaceManager(self.test_root)

    def tearDown(self):
        """测试后清理临时工作目录"""
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    def test_workspace_creation(self):
        """测试工作空间的创建"""
        # 设置3个工作空间
        self.assertTrue(self.manager.set_workspace_count(3))
        self.assertEqual(len(self.manager.workspaces), 3)
        
        # 验证目录名称
        workspace_names = sorted(os.listdir(self.test_root))
        self.assertEqual(workspace_names, ['ws0', 'ws1', 'ws2'])

    def test_workspace_allocation(self):
        """测试工作空间的分配和释放"""
        self.manager.set_workspace_count(2)
        
        # 分配工作空间
        ws1 = self.manager.alloc("task1")
        self.assertIsNotNone(ws1)
        self.assertEqual(ws1.taskid, "task1")
        
        ws2 = self.manager.alloc("task2")
        self.assertIsNotNone(ws2)
        self.assertEqual(ws2.taskid, "task2")
        
        # 所有工作空间都被占用，应该无法再分配
        ws3 = self.manager.alloc("task3")
        self.assertIsNone(ws3)
        
        # 释放工作空间
        self.assertTrue(self.manager.free(ws1))
        self.assertIsNone(ws1.taskid)
        
        # 现在应该可以再次分配
        ws4 = self.manager.alloc("task4")
        self.assertIsNotNone(ws4)
        self.assertEqual(ws4.taskid, "task4")

    def test_workspace_count_adjustment(self):
        """测试工作空间数量的调整"""
        # 初始创建3个工作空间
        self.manager.set_workspace_count(3)
        self.assertEqual(len(self.manager.workspaces), 3)
        
        # 分配一个工作空间
        ws = self.manager.alloc("task1")
        self.assertIsNotNone(ws)
        
        # 尝试减少到2个工作空间（应该成功，因为仅有一个工作空间被占用）
        self.assertTrue(self.manager.set_workspace_count(2))
        self.assertEqual(len(self.manager.workspaces), 2)
        
        # 尝试减少到0个工作空间（应该失败，因为一个工作空间被占用）
        self.assertFalse(self.manager.set_workspace_count(0))
        self.assertEqual(len(self.manager.workspaces), 2)
        
        # 增加到4个工作空间
        self.assertTrue(self.manager.set_workspace_count(4))
        self.assertEqual(len(self.manager.workspaces), 4)


if __name__ == '__main__':
    unittest.main()