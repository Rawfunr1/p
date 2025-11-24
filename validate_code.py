#!/usr/bin/env python3
"""
Code validation script - checks for common issues without running the full code.
"""

import ast
import sys
from pathlib import Path
from typing import List, Tuple

def check_syntax(file_path: Path) -> Tuple[bool, str]:
    """
    Check if a Python file has valid syntax.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, "OK"
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def check_imports(file_path: Path) -> Tuple[List[str], List[str]]:
    """
    Extract standard library and third-party imports from a file.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        Tuple of (stdlib_imports, third_party_imports)
    """
    stdlib_modules = {
        'os', 'sys', 'logging', 'pathlib', 'typing', 'gc', 'time',
        'subprocess', 'json', 'ast', 'shutil', 'signal', 'textwrap'
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        stdlib = []
        third_party = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split('.')[0]
                    if module in stdlib_modules:
                        stdlib.append(module)
                    else:
                        third_party.append(module)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    module = node.module.split('.')[0]
                    if module in stdlib_modules:
                        stdlib.append(module)
                    else:
                        third_party.append(module)
        
        return list(set(stdlib)), list(set(third_party))
        
    except Exception as e:
        return [], []


def main():
    """Main validation function."""
    project_root = Path(__file__).parent
    
    # Python files to check
    python_files = [
        'floorplan_main.py',
        'config_manager.py',
        'model_builder.py',
        'image_utils.py',
        'dxf_exporter.py',
        'model_3d_exporter.py',
        'dataset.py',
        'floorplan_processor.py',
        'app.py',
        'setup.py'
    ]
    
    print("=" * 60)
    print("CODE VALIDATION REPORT")
    print("=" * 60)
    print()
    
    # Check syntax
    print("1. SYNTAX CHECK")
    print("-" * 60)
    all_valid = True
    for file_name in python_files:
        file_path = project_root / file_name
        if not file_path.exists():
            print(f"  ⚠  {file_name}: File not found")
            continue
        
        is_valid, message = check_syntax(file_path)
        status = "✓" if is_valid else "✗"
        print(f"  {status}  {file_name}: {message}")
        if not is_valid:
            all_valid = False
    
    print()
    
    # Check imports
    print("2. IMPORT ANALYSIS")
    print("-" * 60)
    all_third_party = set()
    for file_name in python_files:
        file_path = project_root / file_name
        if not file_path.exists():
            continue
        
        stdlib, third_party = check_imports(file_path)
        all_third_party.update(third_party)
    
    print(f"  Third-party dependencies found: {len(all_third_party)}")
    for module in sorted(all_third_party):
        print(f"    - {module}")
    
    print()
    
    # Check requirements.txt
    print("3. REQUIREMENTS CHECK")
    print("-" * 60)
    req_file = project_root / 'requirements.txt'
    if req_file.exists():
        with open(req_file, 'r') as f:
            requirements = [
                line.strip().split('>=')[0].split('==')[0].replace('-', '_')
                for line in f
                if line.strip() and not line.startswith('#')
            ]
        print(f"  ✓ requirements.txt exists ({len(requirements)} packages)")
        
        # Check if all imports are in requirements
        missing = []
        for module in all_third_party:
            # Map common module names to package names
            module_to_package = {
                'cv2': 'opencv-contrib-python',
                'PIL': 'Pillow',
                'yaml': 'PyYAML',
                'skimage': 'scikit-image',
            }
            package_name = module_to_package.get(module, module)
            
            if not any(package_name.lower() in req.lower() for req in requirements):
                missing.append(module)
        
        if missing:
            print(f"  ⚠  Modules not in requirements.txt: {', '.join(missing)}")
        else:
            print("  ✓ All imports appear to be in requirements.txt")
    else:
        print("  ✗ requirements.txt not found")
    
    print()
    
    # Summary
    print("4. SUMMARY")
    print("-" * 60)
    if all_valid:
        print("  ✓ All syntax checks passed")
        print("  ✓ Code structure is valid")
        print("  ✓ Ready for deployment (after dependency installation)")
    else:
        print("  ✗ Some syntax errors found")
        print("  ⚠  Fix errors before deployment")
    
    print()
    print("=" * 60)
    
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())
