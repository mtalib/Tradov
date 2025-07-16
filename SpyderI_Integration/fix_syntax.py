#!/usr/bin/env python3
"""
Quick fix script for syntax error in SpyderI01_IntegrationHub.py
"""

import re
import sys

def fix_syntax_error(filename):
    """Fix common syntax errors in error handler calls."""
    
    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
        
        # Look for line 832 and surrounding lines
        if len(lines) >= 832:
            print(f"Line 830: {lines[829].rstrip()}")
            print(f"Line 831: {lines[830].rstrip()}")
            print(f"Line 832: {lines[831].rstrip()}")
            print(f"Line 833: {lines[832].rstrip()}" if len(lines) > 832 else "")
            print(f"Line 834: {lines[833].rstrip()}" if len(lines) > 833 else "")
            
            # Check for unclosed brackets
            line_832 = lines[831]
            open_braces = line_832.count('{')
            close_braces = line_832.count('}')
            open_parens = line_832.count('(')
            close_parens = line_832.count(')')
            
            print(f"\nLine 832 analysis:")
            print(f"  Open braces '{': {open_braces}")
            print(f"  Close braces '}': {close_braces}")
            print(f"  Open parens '(': {open_parens}")
            print(f"  Close parens ')': {close_parens}")
            
            # Try to fix common patterns
            if 'self.error_handler.handle_error(e, {' in line_832:
                # Check if the dict is properly closed
                # Count brackets from this point forward
                bracket_count = 0
                paren_count = 0
                in_string = False
                quote_char = None
                
                for i in range(831, min(len(lines), 850)):
                    line = lines[i]
                    for char in line:
                        if not in_string:
                            if char in ['"', "'"]:
                                in_string = True
                                quote_char = char
                            elif char == '{':
                                bracket_count += 1
                            elif char == '}':
                                bracket_count -= 1
                            elif char == '(':
                                paren_count += 1
                            elif char == ')':
                                paren_count -= 1
                        else:
                            if char == quote_char and line[line.index(char)-1] != '\\':
                                in_string = False
                                quote_char = None
                    
                    if bracket_count == 0 and paren_count == 0:
                        print(f"\nBrackets balance at line {i+1}")
                        break
                
                if bracket_count != 0 or paren_count != 0:
                    print(f"\nUnbalanced brackets/parens detected!")
                    print(f"  Bracket balance: {bracket_count}")
                    print(f"  Paren balance: {paren_count}")
                    
                    # Try to fix by adding closing brackets/parens
                    fix_line = 831
                    while fix_line < len(lines) and not lines[fix_line].strip().endswith(')'):
                        fix_line += 1
                    
                    if fix_line < len(lines):
                        # Add missing closing bracket before the closing paren
                        lines[fix_line] = lines[fix_line].rstrip()
                        if not lines[fix_line].endswith('}'):
                            lines[fix_line] = lines[fix_line].rstrip(')') + '})' + '\n'
                            print(f"\nFixed line {fix_line + 1}: {lines[fix_line].rstrip()}")
                            
                            # Write the fixed file
                            with open(filename + '.fixed', 'w') as f:
                                f.writelines(lines)
                            print(f"\nFixed file saved as: {filename}.fixed")
                            return True
        
    except Exception as e:
        print(f"Error reading file: {e}")
        return False
    
    return False

if __name__ == "__main__":
    filename = "SpyderI_Integration/SpyderI01_IntegrationHub.py"
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    
    print(f"Analyzing {filename} for syntax errors...")
    if fix_syntax_error(filename):
        print("\nTo apply the fix:")
        print(f"  mv {filename} {filename}.backup")
        print(f"  mv {filename}.fixed {filename}")
    else:
        print("\nCould not automatically fix. Manual inspection required.")
        print("\nCommon fix patterns:")
        print("1. If you see: self.error_handler.handle_error(e, {")
        print("   Make sure it ends with: })")
        print("\n2. Check that all dictionary entries have commas between them")
        print("\n3. Ensure all opening brackets have matching closing brackets")
