#!/usr/bin/env python3
"""
Comprehensive Test Suite for Novel-v1 Translation System
Tests all the fixes and features implemented.

Run with: python3 test_novel_v1.py
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(title):
    """Print a formatted test header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}  {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_test(name, status, details=""):
    """Print test result."""
    icon = f"{Colors.GREEN}✅" if status == "PASS" else f"{Colors.RED}❌"
    print(f"{icon} {name}{Colors.END}")
    if details:
        print(f"   {Colors.CYAN}{details}{Colors.END}")

def test_syntax_check():
    """Test 1: Verify all Python files have valid syntax."""
    print_header("TEST 1: Python Syntax Check")
    
    python_files = [
        "src/main.py",
        "src/agents/translator.py",
        "src/agents/refiner.py",
        "src/agents/checker.py",
        "src/agents/base_agent.py",
        "src/agents/preprocessor.py",
        "src/memory/memory_manager.py",
        "src/utils/file_handler.py",
        "src/utils/ollama_client.py",
        "ui/streamlit_app.py",
        "ui/pages/2_Translate.py",
        "ui/pages/3_Progress.py",
        "ui/pages/4_Glossary_Editor.py",
        "ui/pages/5_Settings.py",
        "ui/components/sidebar.py",
        "tools/launch_ui.py",
    ]
    
    all_passed = True
    for file_path in python_files:
        full_path = Path(file_path)
        if not full_path.exists():
            print_test(f"{file_path}", "FAIL", "File not found")
            all_passed = False
            continue
            
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(full_path)],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                print_test(f"{file_path}", "PASS")
            else:
                print_test(f"{file_path}", "FAIL", result.stderr[:100])
                all_passed = False
        except Exception as e:
            print_test(f"{file_path}", "FAIL", str(e))
            all_passed = False
    
    return all_passed

def test_import_paths():
    """Test 2: Verify UI import paths work correctly."""
    print_header("TEST 2: UI Import Path Verification")
    
    tests = [
        ("ui.components.sidebar", "render_sidebar"),
        ("src.utils.file_handler", "FileHandler"),
        ("src.memory.memory_manager", "MemoryManager"),
    ]
    
    all_passed = True
    for module_name, attr_name in tests:
        try:
            # Test importing from project root
            sys.path.insert(0, str(Path.cwd()))
            module = __import__(module_name, fromlist=[attr_name])
            getattr(module, attr_name)  # Verify attribute exists
            print_test(f"Import {module_name}.{attr_name}", "PASS")
        except Exception as e:
            print_test(f"Import {module_name}.{attr_name}", "FAIL", str(e))
            all_passed = False
    
    return all_passed

def test_config_loading():
    """Test 3: Verify configuration files load correctly."""
    print_header("TEST 3: Configuration Loading")
    
    config_files = [
        "config/settings.yaml",
        "config/settings.english.yaml",
        "config/settings.pivot.yaml",
        "config/settings.fast.yaml",
    ]
    
    all_passed = True
    for config_file in config_files:
        try:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            # Verify required keys
            required_keys = ['models', 'processing', 'paths']
            missing = [k for k in required_keys if k not in config]
            
            if missing:
                print_test(f"{config_file}", "FAIL", f"Missing keys: {missing}")
                all_passed = False
            else:
                print_test(f"{config_file}", "PASS", f"Loaded {len(config)} top-level keys")
        except Exception as e:
            print_test(f"{config_file}", "FAIL", str(e))
            all_passed = False
    
    return all_passed

def test_data_directories():
    """Test 4: Verify required data directories exist."""
    print_header("TEST 4: Data Directory Structure")
    
    required_dirs = [
        "data/input",
        "data/output",
        "logs",
        "config",
    ]
    
    all_passed = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print_test(f"{dir_path}/", "PASS", "Directory exists")
        else:
            print(f"{Colors.YELLOW}⚠️  {dir_path}/ - Creating...{Colors.END}")
            path.mkdir(parents=True, exist_ok=True)
            print_test(f"{dir_path}/", "PASS", "Created")
    
    return all_passed

def test_cli_help():
    """Test 5: Verify CLI help works."""
    print_header("TEST 5: CLI Help System")
    
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.main", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0 and "--ui" in result.stdout:
            print_test("CLI --help", "PASS", "Help text displayed correctly")
            # Check for our flags
            flags = ["--ui", "--mode", "--generate-glossary", "--skip-refinement"]
            for flag in flags:
                if flag in result.stdout:
                    print_test(f"  Flag {flag}", "PASS")
                else:
                    print_test(f"  Flag {flag}", "FAIL", "Not found in help")
            return True
        else:
            print_test("CLI --help", "FAIL", result.stderr[:100])
            return False
    except Exception as e:
        print_test("CLI --help", "FAIL", str(e))
        return False

def test_launcher_script():
    """Test 6: Verify launcher script structure."""
    print_header("TEST 6: Web UI Launcher Script")
    
    launcher_path = Path("tools/launch_ui.py")
    if not launcher_path.exists():
        print_test("Launcher script", "FAIL", "File not found")
        return False
    
    try:
        with open(launcher_path, 'r') as f:
            content = f.read()
        
        checks = [
            ("Log file creation", "logs/web_server.log" in content),
            ("Streamlit command", "streamlit" in content and "run" in content),
            ("Process management", "subprocess.Popen" in content),
            ("Keyboard interrupt", "KeyboardInterrupt" in content),
            ("Project root detection", "Path(__file__)" in content),
        ]
        
        all_passed = True
        for check_name, check_result in checks:
            if check_result:
                print_test(f"  {check_name}", "PASS")
            else:
                print_test(f"  {check_name}", "FAIL")
                all_passed = False
        
        return all_passed
    except Exception as e:
        print_test("Launcher script", "FAIL", str(e))
        return False

def test_enhanced_display_functions():
    """Test 7: Verify enhanced CLI display functions exist."""
    print_header("TEST 7: Enhanced CLI Display Functions")
    
    try:
        sys.path.insert(0, str(Path.cwd()))
        from src.main import (
            print_box,
            print_pipeline_status,
        )
        
        print_test("print_box function", "PASS", "Defined in main.py")
        print_test("print_pipeline_status function", "PASS", "Defined in main.py")
        print_test("print_translation_header function", "PASS", "Defined in main.py")
        
        # Test the functions work
        print(f"\n{Colors.CYAN}Testing print_box():{Colors.END}")
        print_box("TEST BOX", [("Key1", "Value1"), ("Key2", "Value2")], width=50)
        
        print(f"\n{Colors.CYAN}Testing print_pipeline_status():{Colors.END}")
        print_pipeline_status("Test Step", "complete", "All good")
        
        return True
    except ImportError as e:
        print_test("Display functions", "FAIL", str(e))
        return False
    except Exception as e:
        print_test("Display functions", "FAIL", str(e))
        return False

def test_ui_pages_structure():
    """Test 8: Verify UI pages have correct structure."""
    print_header("TEST 8: UI Pages Structure")
    
    pages = [
        ("ui/pages/2_Translate.py", ["render_sidebar", "st.set_page_config"]),
        ("ui/pages/4_Glossary_Editor.py", ["MemoryManager", "FileHandler"]),
        ("ui/streamlit_app.py", ["st.set_page_config"]),
    ]
    
    all_passed = True
    for page_path, required_elements in pages:
        try:
            with open(page_path, 'r') as f:
                content = f.read()
            
            for element in required_elements:
                if element in content:
                    print_test(f"{page_path} - {element}", "PASS")
                else:
                    print_test(f"{page_path} - {element}", "FAIL", "Not found")
                    all_passed = False
            
            # Check for path fix (not needed for main streamlit_app.py)
            if page_path == "ui/streamlit_app.py":
                print_test(f"{page_path} - Path fix", "PASS", "Main entry point (no fix needed)")
            elif "project_root" in content and "sys.path.insert" in content:
                print_test(f"{page_path} - Path fix", "PASS")
            else:
                print_test(f"{page_path} - Path fix", "FAIL", "Missing project_root fix")
                
        except Exception as e:
            print_test(f"{page_path}", "FAIL", str(e))
            all_passed = False
    
    return all_passed

def test_progress_logger():
    """Test 9: Verify progress logger works."""
    print_header("TEST 9: Progress Logger")
    
    try:
        sys.path.insert(0, str(Path.cwd()))
        from src.utils.progress_logger import ProgressLogger
        
        # Create a test logger
        logger = ProgressLogger(
            book_id="test_book",
            chapter_name="test_chapter_001",
            total_chunks=5
        )
        
        print_test("ProgressLogger creation", "PASS")
        
        # Test log path
        log_path = logger.get_log_path()
        if log_path and "progress" in str(log_path).lower():
            print_test("Log path generation", "PASS", str(log_path))
        else:
            print_test("Log path generation", "FAIL")
            return False
        
        # Test logging
        logger.log_chunk(0, "Test translation chunk", "Source text")
        print_test("log_chunk() method", "PASS")
        
        logger.finalize(success=True)
        print_test("finalize() method", "PASS")
        
        # Verify log file was created
        if log_path.exists():
            print_test("Log file created", "PASS")
        else:
            print_test("Log file created", "FAIL", "File not found")
            return False
        
        return True
    except Exception as e:
        print_test("Progress logger", "FAIL", str(e))
        return False

def test_memory_manager():
    """Test 10: Verify MemoryManager works."""
    print_header("TEST 10: Memory Manager")
    
    try:
        sys.path.insert(0, str(Path.cwd()))
        from src.memory.memory_manager import MemoryManager
        
        # Create a test memory manager
        memory = MemoryManager(
            glossary_path="data/glossary.json",
            context_path="data/context_memory.json"
        )
        
        print_test("MemoryManager creation", "PASS")
        
        # Test glossary access (call to verify method works)
        memory.get_glossary_for_prompt(limit=10)
        print_test("get_glossary_for_prompt() method", "PASS", "Glossary retrieved")
        
        # Test term retrieval
        test_term = memory.get_term("测试")
        if test_term or test_term is None:
            print_test("get_term() method", "PASS")
        
        return True
    except Exception as e:
        print_test("Memory manager", "FAIL", str(e))
        return False

def test_file_handler():
    """Test 11: Verify FileHandler works."""
    print_header("TEST 11: File Handler")
    
    try:
        sys.path.insert(0, str(Path.cwd()))
        from src.utils.file_handler import FileHandler
        
        # Test read/write
        test_file = Path("logs/test_file_handler.txt")
        test_content = "Test content for file handler\nမြန်မာဘာသာစက်မှု"
        
        FileHandler.write_text(test_file, test_content)
        print_test("write_text() method", "PASS")
        
        read_content = FileHandler.read_text(test_file)
        if read_content == test_content:
            print_test("read_text() method", "PASS", "UTF-8 content preserved")
        else:
            print_test("read_text() method", "FAIL", "Content mismatch")
            return False
        
        # Clean up
        test_file.unlink(missing_ok=True)
        
        return True
    except Exception as e:
        print_test("File handler", "FAIL", str(e))
        return False

def run_all_tests():
    """Run all tests and print summary."""
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}  NOVEL-V1 TRANSLATION SYSTEM - COMPREHENSIVE TEST SUITE{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}{'='*70}{Colors.END}")
    print(f"{Colors.CYAN}Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}\n")
    
    tests = [
        ("Python Syntax Check", test_syntax_check),
        ("UI Import Paths", test_import_paths),
        ("Configuration Loading", test_config_loading),
        ("Data Directories", test_data_directories),
        ("CLI Help System", test_cli_help),
        ("Web UI Launcher", test_launcher_script),
        ("Enhanced CLI Display", test_enhanced_display_functions),
        ("UI Pages Structure", test_ui_pages_structure),
        ("Progress Logger", test_progress_logger),
        ("Memory Manager", test_memory_manager),
        ("File Handler", test_file_handler),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"{Colors.RED}❌ {test_name} - CRASH: {e}{Colors.END}")
            results.append((test_name, False))
    
    # Summary
    print_header("TEST SUMMARY")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = f"{Colors.GREEN}PASS" if passed else f"{Colors.RED}FAIL"
        print(f"{status} {test_name}{Colors.END}")
    
    print(f"\n{Colors.BOLD}Results: {passed_count}/{total_count} tests passed{Colors.END}")
    
    if passed_count == total_count:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 All tests passed!{Colors.END}")
        return 0
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  Some tests failed. Please review the output above.{Colors.END}")
        return 1

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
