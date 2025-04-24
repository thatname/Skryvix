import unittest
import os
import aiofiles
from unittest.mock import AsyncMock, patch
from read_file_tool import ReadFileTool

class TestReadFileTool(unittest.TestCase):
    def setUp(self):
        self.tool = ReadFileTool()
        # Create test files
        self.test_file1 = "test_file1.txt"
        self.test_file2 = "test_file2.txt"
        self.test_content1 = "Test content 1"
        self.test_content2 = "Test content 2"
        
        with open(self.test_file1, 'w') as f:
            f.write(self.test_content1)
        with open(self.test_file2, 'w') as f:
            f.write(self.test_content2)

    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_file1):
            os.remove(self.test_file1)
        if os.path.exists(self.test_file2):
            os.remove(self.test_file2)

    async def test_read_single_file(self):
        """Test reading a single existing file"""
        result = []
        async for output in self.tool.use(self.test_file1):
            result.append(output)
        
        self.assertEqual(len(result), 1)
        self.assertIn(self.test_content1, result[0])
        self.assertIn(f"File: {self.test_file1}", result[0])

    async def test_read_multiple_files(self):
        """Test reading multiple files at once"""
        input_files = f"{self.test_file1}\n{self.test_file2}"
        result = []
        async for output in self.tool.use(input_files):
            result.append(output)
        
        self.assertEqual(len(result), 2)
        self.assertIn(self.test_content1, result[0])
        self.assertIn(self.test_content2, result[1])

    async def test_file_not_found(self):
        """Test handling of non-existent file"""
        result = []
        async for output in self.tool.use("nonexistent.txt"):
            result.append(output)
        
        self.assertEqual(len(result), 1)
        self.assertIn("Error: File not found - nonexistent.txt", result[0])

    @patch.object(ReadFileTool, '_fuzzy_match', new_callable=AsyncMock)
    async def test_fuzzy_matching(self, mock_fuzzy):
        """Test fuzzy matching functionality"""
        mock_fuzzy.return_value = self.test_file1
        result = []
        async for output in self.tool.use("similar_name.txt"):
            result.append(output)
        
        mock_fuzzy.assert_called_once_with("similar_name.txt")
        self.assertEqual(len(result), 1)
        self.assertIn(f"Matched: {self.test_file1}", result[0])
        self.assertIn(self.test_content1, result[0])

    @patch.object(ReadFileTool, '_fuzzy_match', new_callable=AsyncMock)
    async def test_fuzzy_matching_failure(self, mock_fuzzy):
        """Test when fuzzy matching fails"""
        mock_fuzzy.return_value = None
        result = []
        async for output in self.tool.use("unknown.txt"):
            result.append(output)
        
        self.assertEqual(len(result), 1)
        self.assertIn("Error: File not found - unknown.txt", result[0])

    async def test_empty_path(self):
        """Test handling of empty path in input"""
        result = []
        async for output in self.tool.use("\n\n"):
            result.append(output)
        
        self.assertEqual(len(result), 0)

    @unittest.skipIf(os.name == 'nt', "Permission test not reliable on Windows")
    async def test_permission_error(self):
        """Test handling of permission denied error"""
        # Make file unreadable
        os.chmod(self.test_file1, 0o000)
        try:
            result = []
            async for output in self.tool.use(self.test_file1):
                result.append(output)
            
            self.assertEqual(len(result), 1)
            self.assertIn("Error: Permission denied", result[0])
        finally:
            # Restore permissions for cleanup
            os.chmod(self.test_file1, 0o644)

if __name__ == '__main__':
    unittest.main()
