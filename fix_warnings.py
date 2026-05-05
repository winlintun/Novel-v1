import re

with open('tests/test_novel_v1.py', 'r') as f:
    content = f.read()

content = content.replace('return all_passed', 'assert all_passed')
content = content.replace('return True', 'return')
content = content.replace('return False', 'assert False')

old_runner = """    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"{Colors.RED}❌ {test_name} - CRASH: {e}{Colors.END}")
            results.append((test_name, False))"""

new_runner = """    results = []
    for test_name, test_func in tests:
        try:
            test_func()
            results.append((test_name, True))
        except AssertionError as e:
            # test_func uses assert to fail, which raises AssertionError
            # We catch it here to mark the test as failed without crashing the runner
            results.append((test_name, False))
        except Exception as e:
            print(f"{Colors.RED}❌ {test_name} - CRASH: {e}{Colors.END}")
            results.append((test_name, False))"""

content = content.replace(old_runner, new_runner)

with open('tests/test_novel_v1.py', 'w') as f:
    f.write(content)
